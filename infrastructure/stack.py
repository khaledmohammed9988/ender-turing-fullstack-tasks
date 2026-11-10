"""CloudFormation with no inbound rules and no secrets in template or user data."""

import base64
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build_template():
    images = json.loads((HERE / "images.lock.json").read_text())["images"]
    image_env = "\n".join(f"{key}={value}" for key, value in images.items()) + "\n"
    compose = base64.b64encode((HERE / "compose.yaml").read_bytes()).decode()
    env = base64.b64encode(image_env.encode()).decode()
    bootstrap = (HERE / "bootstrap.sh").read_text()
    userdata = {
        "Fn::Base64": {
            "Fn::Join": [
                "",
                [
                    "#!/bin/bash\nset -Eeuo pipefail\n",
                    "export AWS_DEFAULT_REGION='",
                    {"Ref": "AWS::Region"},
                    "'\n",
                    "export TUNNEL_TOKEN_PARAMETER='",
                    {"Ref": "TunnelTokenParameter"},
                    "'\n",
                    "export GHOST_URL='",
                    {"Ref": "GhostUrl"},
                    "'\n",
                    "umask 077\ninstall -d -m 0700 /opt/ender-ghost\n",
                    f"echo '{compose}' | base64 -d > /opt/ender-ghost/compose.yaml\n",
                    f"echo '{env}' | base64 -d > /opt/ender-ghost/images.env\n",
                    bootstrap,
                ],
            ]
        }
    }
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Review draft: Ghost/MySQL via outbound Cloudflare Tunnel; no public SSH or web ports.",
        "Parameters": {
            "GhostUrl": {
                "Type": "String",
                "AllowedPattern": r"https://[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]",
                "Description": "Existing tunnel HTTPS hostname, no path or query",
            },
            "TunnelTokenParameter": {
                "Type": "String",
                "AllowedPattern": r"/[a-zA-Z0-9_./-]+",
                "Description": "Existing SSM SecureString parameter path; use AWS-managed SSM KMS key",
            },
            "AmiId": {
                "Type": "AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>",
                "Default": "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64",
            },
            "InstanceType": {
                "Type": "String",
                "Default": "t3.small",
                "AllowedValues": ["t3.small", "t3.medium"],
            },
        },
        "Resources": {
            "Vpc": {
                "Type": "AWS::EC2::VPC",
                "Properties": {
                    "CidrBlock": "10.72.0.0/16",
                    "EnableDnsSupport": True,
                    "EnableDnsHostnames": True,
                },
            },
            "InternetGateway": {"Type": "AWS::EC2::InternetGateway"},
            "GatewayAttachment": {
                "Type": "AWS::EC2::VPCGatewayAttachment",
                "Properties": {
                    "VpcId": {"Ref": "Vpc"},
                    "InternetGatewayId": {"Ref": "InternetGateway"},
                },
            },
            "Subnet": {
                "Type": "AWS::EC2::Subnet",
                "Properties": {
                    "VpcId": {"Ref": "Vpc"},
                    "CidrBlock": "10.72.1.0/24",
                    "MapPublicIpOnLaunch": False,
                },
            },
            "RouteTable": {
                "Type": "AWS::EC2::RouteTable",
                "Properties": {"VpcId": {"Ref": "Vpc"}},
            },
            "Route": {
                "Type": "AWS::EC2::Route",
                "DependsOn": "GatewayAttachment",
                "Properties": {
                    "RouteTableId": {"Ref": "RouteTable"},
                    "DestinationCidrBlock": "0.0.0.0/0",
                    "GatewayId": {"Ref": "InternetGateway"},
                },
            },
            "SubnetRoute": {
                "Type": "AWS::EC2::SubnetRouteTableAssociation",
                "Properties": {
                    "RouteTableId": {"Ref": "RouteTable"},
                    "SubnetId": {"Ref": "Subnet"},
                },
            },
            "NoIngress": {
                "Type": "AWS::EC2::SecurityGroup",
                "Properties": {
                    "GroupDescription": "No inbound traffic, including SSH, HTTP and HTTPS",
                    "VpcId": {"Ref": "Vpc"},
                    "SecurityGroupIngress": [],
                    "SecurityGroupEgress": [
                        {
                            "IpProtocol": "-1",
                            "CidrIp": "0.0.0.0/0",
                            "Description": "Outbound package pulls, SSM and tunnel only; no inbound listeners",
                        }
                    ],
                },
            },
            "InstanceRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "AssumeRolePolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"Service": "ec2.amazonaws.com"},
                                "Action": "sts:AssumeRole",
                            }
                        ],
                    },
                    "Policies": [
                        {
                            "PolicyName": "ReadOneTunnelToken",
                            "PolicyDocument": {
                                "Version": "2012-10-17",
                                "Statement": [
                                    {
                                        "Effect": "Allow",
                                        "Action": "ssm:GetParameter",
                                        "Resource": {
                                            "Fn::Sub": "arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter${TunnelTokenParameter}"
                                        },
                                    }
                                ],
                            },
                        },
                        {
                            "PolicyName": "SessionManagerChannels",
                            "PolicyDocument": {
                                "Version": "2012-10-17",
                                "Statement": [
                                    {
                                        "Effect": "Allow",
                                        "Action": [
                                            "ssm:UpdateInstanceInformation",
                                            "ssmmessages:CreateControlChannel",
                                            "ssmmessages:CreateDataChannel",
                                            "ssmmessages:OpenControlChannel",
                                            "ssmmessages:OpenDataChannel",
                                        ],
                                        "Resource": "*",
                                    }
                                ],
                            },
                        },
                    ],
                },
            },
            "InstanceProfile": {
                "Type": "AWS::IAM::InstanceProfile",
                "Properties": {"Roles": [{"Ref": "InstanceRole"}]},
            },
            "GhostVm": {
                "Type": "AWS::EC2::Instance",
                "DependsOn": ["Route", "SubnetRoute"],
                "Properties": {
                    "ImageId": {"Ref": "AmiId"},
                    "InstanceType": {"Ref": "InstanceType"},
                    "IamInstanceProfile": {"Ref": "InstanceProfile"},
                    "MetadataOptions": {
                        "HttpTokens": "required",
                        "HttpPutResponseHopLimit": 1,
                        "HttpEndpoint": "enabled",
                    },
                    "NetworkInterfaces": [
                        {
                            "DeviceIndex": "0",
                            "AssociatePublicIpAddress": True,
                            "SubnetId": {"Ref": "Subnet"},
                            "GroupSet": [{"Ref": "NoIngress"}],
                        }
                    ],
                    "BlockDeviceMappings": [
                        {
                            "DeviceName": "/dev/xvda",
                            "Ebs": {
                                "VolumeSize": 20,
                                "VolumeType": "gp3",
                                "Encrypted": True,
                                "DeleteOnTermination": True,
                            },
                        }
                    ],
                    "UserData": userdata,
                    "Tags": [
                        {"Key": "Name", "Value": {"Fn::Sub": "${AWS::StackName}-ghost"}}
                    ],
                },
            },
        },
        "Outputs": {
            "InstanceId": {"Value": {"Ref": "GhostVm"}},
            "GhostUrl": {"Value": {"Ref": "GhostUrl"}},
        },
    }


if __name__ == "__main__":
    print(json.dumps(build_template(), indent=2))

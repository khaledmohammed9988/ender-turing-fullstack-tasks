# Review notes and limitations

- This is an AI-assisted application exercise, not evidence of a previous client delivery. Review the implementation and the task-specific AI record before sharing it.
- The employer suggests about an hour for the development task. This preparation included additional automated verification and infrastructure work; no claim of meeting that timebox is made.
- The base is the actual FastAPI full-stack template, commit `aabb90126964a164e02aff39e7c385bb0598236d`. The upstream MIT license is retained.
- The RBAC design has three fixed roles, not a general policy editor or multi-tenant authorization system. UI visibility may remain stale after an administrator changes a logged-in user's role until the next refresh; the backend reads the current database role on every request and denies unauthorized operations immediately.
- The existing `is_superuser` database column is retained as a compatibility mirror. It is not an input field or an authority source. Old clients that write that field must migrate to the `role` contract.
- Downgrading the role migration necessarily loses the manager/member distinction. Administrators are preserved in the old boolean; a re-upgrade turns old non-admins into members. Take a backup before any production downgrade.
- The unprotected development `/private/users/` helper is not registered, even in development. Demo accounts require an explicit operator password and a development environment.
- AWS deployment has NOT been executed. Ghost/MySQL compatibility, restart persistence and independent authenticated HTTPS access were subsequently verified in a temporary Daytona Docker sandbox. That test used Daytona's preview proxy after Cloudflare Quick Tunnel registration encountered connection resets. It does not verify AWS IAM/SSM/cloud-init, the named Cloudflare connector or production readiness. See `docs/runtime-validation.md`.
- The deployment command supports initial provisioning. It refuses an existing stack rather than pretending that an EC2 user-data update automatically reruns cloud-init. Inspect failed stacks through SSM and review recovery/backup plans before changes.
- The VM has a public IPv4 address for outbound connectivity and no inbound security-group rules. There is no SSH key, public web port or host-published container port. This is tunnel-only inbound access, not a private-subnet design. Outbound traffic is unrestricted.
- Ghost content and MySQL persist in Docker volumes on the instance root disk. Stack deletion terminates the instance and deletes that disk. Backups, restore drills, mail delivery, application updates and high availability are outside this exercise.
- Set up Cloudflare Access protection for the Ghost admin path and claim the owner account before opening the site to others. Do not paste AWS credentials, the tunnel token, private environment files or unrelated chat history into the repository.

See `docs/validation.md` for the final verification scope and the local review evidence.

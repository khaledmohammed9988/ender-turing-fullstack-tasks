# Review before sharing

- [ ] Read the role matrix and three design paragraphs in `README.md`.
- [ ] Inspect the admin/manager/member screenshots in `.evidence/` and the implementation diff against the pinned upstream commit.
- [ ] Review the signup/profile protection, admin-only role assignment, existing-token behavior and self-lockout prevention.
- [ ] Review the migration's lossy downgrade and the development-only seed policy.
- [ ] Read `infrastructure/README.md`, including the existing Cloudflare tunnel/DNS and SSM-token prerequisites.
- [ ] Decide whether to authorize a paid AWS smoke test. None has been executed; unit/static checks do not prove a working VM/tunnel deployment.
- [ ] Review the AI assistance record. Add a reviewed original chat export if the employer requests a complete transcript.
- [ ] Check the repository for secrets and unrelated/private data before publication. `.env`, `.tools`, `.evidence`, `.review` and generated deployment state are excluded from Git.
- [ ] Review inherited upstream CI/release/deployment workflows separately before enabling them or adding secrets.
- [ ] Only after review: choose the GitHub destination and authorize publication, then prepare the Full-Stack application with the repository URL and motivation note.

Preparation itself did not publish, submit an application, create an AWS stack or sign anything.

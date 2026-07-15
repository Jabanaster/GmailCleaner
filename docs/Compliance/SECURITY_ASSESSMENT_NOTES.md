# Security Assessment Notes

- Restricted scope usage (`gmail.readonly`) requires passing a Tier 2 CASA (Cloud Application Security Assessment) security review.
- The backend app must support scanning and vulnerability mitigation (using bandit/safety python packages).
- Database credentials and OAuth secrets must be fully encrypted, stored outside version control, and rotated regularly.

# Protocol Stub Data Policy

Files in this directory are synthetic interoperability fixtures only.

Rules:

- Do not copy historical vendor stub files, manuals, screenshots, customer exports, database dumps, or source code into this directory.
- Do not place real guest, employee, technician, customer, hotel, company, property, or account names inside stub payloads.
- Use neutral placeholders such as `GUESTLAST`, `GUESTFIRST`, `PROPERTY`, `ROOM`, and synthetic numbers.
- Third-party names may appear only where they are intentionally used as a compatibility/profile identifier, such as `Mitel 1` or `Mitel 2`; they must not be embedded as sample customer/company data.
- Stubs should contain only the minimum factual wire examples needed for regression testing.
- Any future imported fixture must be sanitized before it is committed.

The current Mitel fixtures were recreated from protocol behavior and sanitized test observations. They are not copies of any third-party stub file.

# Practical Interview Scenario

## Borrower exposure across lines of business

You are a business analyst supporting Northstar Credit's Capital Markets team. A Capital Markets user has asked you to investigate a discrepancy for **Alder Ridge Manufacturing (Borrower ID 1042)**. From the end-user's perspective, the issue is:

> “The borrower exposure page currently shows total exposure of **CAD 87,267,500** and **USD 64,621,000**. The Commercial Banking and Wealth Management account managers have separately confirmed that the borrower-wide total should be **CAD 78,934,000** and **USD 58,449,000**. I can see Capital Markets facility details, but I can’t see the facilities in those other lines of business. I don’t know whether a facility amount, the borrower total, or how the page displays it is wrong. I need a reliable borrower total for my current exposure review. Can you investigate and let me know what you find?”

The end-user may share these aggregate figures because the amounts are not sensitive. They cannot provide or see Commercial Banking or Wealth Management facility-level details. They have not relied on the mismatched amount to make a credit decision. The candidate can ask clarifying questions, but these facts and the issue itself are available from the start.

## Exposure definition for this exercise

- Total exposure is the sum of committed and uncommitted amounts for each eligible facility. Drawn amount is not added to exposure; it is a utilization measure.
- Facility utilization is drawn amount divided by committed plus uncommitted amount. Borrower utilization is the sum of drawn amounts divided by the sum of exposure amounts, calculated after conversion to CAD; do not average facility percentages.
- For example, a CAD 5 million credit facility and a CAD 10 million contingent facility represent CAD 15 million in exposure. If CAD 3 million is drawn on the credit facility and nothing is drawn on the contingent facility, overall utilization is 20% (CAD 3 million ÷ CAD 15 million).
- Convert each source-currency amount into both CAD and USD. Show both output currencies for every borrower, including borrowers whose facilities are already denominated in CAD or USD.
- Include facilities whose status is `ACTIVE`, even when their maturity date has passed. Maturity date alone does not change facility status or exposure eligibility. Exclude facilities whose status is not `ACTIVE`, including `CLOSED` and `INACTIVE`.
- Show a borrower-level breakdown across Credit (Lending and Trading) and Non-credit/other (Transactional and Contingent), with facility types beneath each group.
- Lending facility types include term loans and revolving credit. Trading includes derivatives, repos, foreign exchange, and securities lending. Transactional and contingent examples include settlement services, custody and settlement, letters of credit, and performance guarantees.

The sample FX rates are illustrative and fixed for this exercise. They are not intended to represent current market rates.

Each facility has a descriptive summary (up to 255 characters), a maturity date, and a commitment start date whenever a committed amount exists. The description should agree with the facility's type, currency, amounts, and dates.

## Access and data

The user can view facility details only for their assigned line of business. Borrower totals and account-team contacts can include other lines of business. The account-team list may include a Relationship Manager and Credit Manager for each relevant line of business. The user can see those names and roles even when the other line's facility details are not shown in the app.

The app includes a role selector for Superuser and generic Capital Markets, Commercial Banking, and Wealth Management users. Use the Capital Markets role to reproduce the stakeholder's restricted view; use the superuser role to review all facility details when troubleshooting.

The top bar provides an in-app read-only database utility in every user role. It has two modes: a SQL SELECT editor and a visual table-and-field query builder. Its expandable table and column catalog is available in either mode and serves as a data dictionary for SQL. In visual mode, the candidate chooses every join type and both columns for each join; the utility does not infer join conditions. Results can be copied with headers for spreadsheets or exported as CSV. Queries can inspect all records in the app's synthetic SQLite database, while facility details in the borrower page remain scoped by role.

Line-of-business descriptions are held in a lookup table and associated records use short codes. The UI joins to the lookup table to display descriptions.

The repository, source code, and entire synthetic database are candidate-facing. All data is fictional. The database utility is intentionally available in each role for troubleshooting the app's synthetic data; facility visibility in the borrower page remains limited by role. There is no interviewer-only file in the repository.

## Candidate deliverables

Prepare an email reply to the end-user and a Jira Description for handoff to IT. Be ready to give a short verbal playback. You are not expected to write production-ready code.

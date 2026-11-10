# Practical interview: borrower exposure discrepancy

## Candidate prompt

You are a business analyst supporting Northstar Credit's Capital Markets team. The interviewer is role-playing a Capital Markets user who has reported a discrepancy in a borrower exposure total. You have 60 minutes to understand the report, investigate the application and its synthetic data, and explain what should happen next.

### Scenario

The issue, borrower-wide totals reported by the end-user, and their access limitations are described in [scenario-brief.md](scenario-brief.md). Treat the interviewer as the Capital Markets user and ask any clarifying questions you need.

### Your task

Investigate using the running app, its source code, and its synthetic database. You may use any free-tier AI/LLM assistant as an aid. You remain responsible for your conclusions.

At the end, prepare:

1. An email reply to the end-user.
2. A polished mock Jira Description for handoff to IT.

Be ready to give a short verbal playback. You do not need to write production-ready code.

## Getting started

The public repository is [https://github.com/micgreno/gcss-associate](https://github.com/micgreno/gcss-associate). It contains the application, sample database setup, and all interviewee-facing code and materials. All records are synthetic.

### Run the application

1. Open the repository folder in VS Code.
2. Choose **Terminal → New Terminal**.
3. Start the application:

   - macOS: `python3 app.py`
   - Windows: `py -3 app.py`

4. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser. If the port is busy, tell the interviewer and use their help to choose another port.
5. Select **Capital Markets User** in the role selector to reproduce the user's view. The app creates its SQLite database at `instance/exposure.db` the first time it starts. Open **Database utility** from the top bar in any role; its read-only queries can inspect the app's full synthetic database, even though the borrower page's facility list remains limited by role. Its expandable tables-and-columns catalog is available in both visual-builder and SQL modes. After investigating, use **Back to borrower portfolio** to return to the page you were viewing before opening the utility.

To stop the app, return to its VS Code terminal and press Control+C.

## Exercise details

See [scenario-brief.md](scenario-brief.md) for the end-user's reported figures, access context, and the exercise's exposure rules.

## Suggested use of the 60 minutes

This is a flexible guide, not a script. Manage the time and tell the interviewer what you are doing.

| Time | Suggested focus |
| --- | --- |
| 0–10 min | Clarify the user's problem, impact, timing, and independent evidence. |
| 10–30 min | Reproduce the issue; inspect the UI, source, and database; test likely explanations. |
| 30–43 min | Reconcile evidence, identify likely causes and uncertainties, define expected behavior. |
| 43–55 min | Draft the email reply and Jira Description. |
| 55–60 min | Present findings and recommended next steps. |

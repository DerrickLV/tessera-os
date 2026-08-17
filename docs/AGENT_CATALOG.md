# Agent catalog

| Agent | Owns | Key approval boundary |
|---|---|---|
| Executive Assistant | Briefings, priorities, meetings, follow-up drafts | Send or calendar/task changes |
| Project Manager | Plans, milestones, RAID, status | Assignments, publishing, baselines |
| Knowledge Manager | Retrieval, taxonomy, provenance | Metadata/document writes or deletion |
| Proposal Manager | Scope, fee, schedule, proposal drafts | Pricing commitment or delivery |
| Contract Manager | Clause analysis, risk, redline support | Redline delivery, acceptance, signature |
| Due Diligence Manager | Source-backed diligence and open items | External contact or report release |
| Development Manager | Feasibility through construction handoff | Filing, consultant direction, baseline |
| Construction Manager | Safety signals, quality, schedule, cost, change | Field direction or change approval |
| Capital Manager | Underwriting, capital, covenants, investor drafts | Terms, external delivery, funds |
| Automation Manager | Workflow design, tests, runbooks, incidents | Production writes or enablement |
| Intelligence Agent | Market, policy, competitor intelligence | Publishing, alerts, paid sources |
| Codex Engineering Agent | Software design, changes, tests, releases | Repository writes, dependencies, deploy |

Detailed charters live in `specs/agents/`; executable manifests live in `agents/`;
and behavioral instructions live in `prompts/`. A change to one should be reviewed
for corresponding changes in the other two.

# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Product teams at software companies: analysts and product managers who check customer and app-store review feedback several times a week, usually on a laptop. Each person can belong to several projects with a different role in each (owner, analyst, product manager, viewer).

## Product Purpose
ReviewRadar collects product reviews into projects, runs sentiment analysis on them, and helps teams spot and track recurring issues. Success is a team that can go from "what are customers complaining about?" to a tracked issue without leaving the tool, with access controlled per project.

## Operating Context
- Streamlit frontend (`frontend/`) talking to a FastAPI backend; Supabase handles sign-in only.
- Sprint 1 ships: sign in / sign up, create and archive projects, project roles, email invitations (accept / decline / revoke, 7-day expiry), and an in-app notifications inbox.
- Planned next: CSV review import, sentiment analysis, dashboard, issues, export.

## Capabilities and Constraints
- Roles: owner (manage project, members, roles, archive), analyst (import, analyse, correct labels), product manager (dashboard, issues, export), viewer (read only). No platform-wide admin.
- The last owner leaving promotes the longest-standing member; a sole member must archive instead of leaving.
- Invitations are per email and role; pending invitations expire.
- UI must be built with Streamlit components plus injected CSS; no separate JS frontend.

## Brand Commitments
- Name: ReviewRadar.
- Crimson red is the brand accent (user confirmed, 2026-11-06).

## Evidence on Hand
No real customers, metrics, testimonials or usage numbers exist. The reference screenshots show invented stats (SLA, response rate, momentum %); none of these are backed by the API and must not be shown as real.

## Product Principles
1. Access is per project: always make the viewer's role in the current project obvious.
2. Show only what the API knows; no decorative metrics.
3. Pending decisions (invitations to answer) surface first.
4. Destructive actions (archive, remove, leave) are deliberate and explained.

# Technical architecture

REDCap Export Explorer is a local-only Streamlit application with a framework-independent Python processing package. The browser connects only to the Streamlit process on the same computer; application code contains no HTTP client, telemetry, analytics, update checker, cloud API, or external error reporter.

## Boundaries and data lifecycle

Uploaded content is parsed in memory. Original files are never changed. Data are persisted only when the researcher explicitly downloads an export or saves a project. Reports and logs contain structural metadata, not row-level clinical values. File hashes support reproducibility without copying source content.

The UI calls modules under `src/redcap_explorer`: import and metadata parsing, inference/profiling, candidate identifiers, relationship analysis, transformations, validation, exports, reporting, privacy scanning, and configuration validation. This separation permits a future desktop shell or command-line interface.

## Safety model

Relationship cardinality is calculated before joining. One-to-one, one-to-many, and many-to-one joins use pandas cardinality validation. Many-to-many joins are blocked unless an explicit confirmation reaches the engine. Relational output remains the default when repeating tables are present. Required-key failures are errors; duplicate keys and potentially identifying fields are visible warnings and are never silently removed.

Variable names are cleaned deterministically to Stata's 32-character rules with collision suffixes and a crosswalk. Date parsing requires an explicit format in the processing engine. Invalid numeric/date conversions raise rather than silently becoming missing.

## Phase boundaries

Version 0.2 delivers Phase 2 REDCap awareness: normalized dictionary metadata, coded and checkbox value labels, four checkbox output modes, longitudinal/repeating-grain confirmation, saved-project download/reload, blocking schema-drift checks, metadata comparison, and in-memory relational Stata exports. Rich interactive transformation builders, extended Stata missing values, guided schema-resolution mappings, and desktop packaging remain Phase 3 work.

Version 0.3 adds reproducible preparation recipes, explicit schema remapping, guarded flat exports, richer output summaries, and an optional PyInstaller desktop recipe. Desktop and Streamlit entry points call the same processing modules and preserve the localhost-only boundary.

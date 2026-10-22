# Contributing

Use a branch and a pull request. Explain the user-visible behavior, add meaningful tests for persistence or runtime changes, and update the changelog. Use synthetic entity names and rooms in tests and screenshots. Never commit a Home Assistant configuration, token, service account or recovery snapshot.

Run the checks in the README. Changes to the runtime adapter need tests against the actual Home Assistant GoogleConfig implementation. Keep authentication checks, stale-revision protection, external-file conflict detection and recovery behavior intact. Keep frontend dependencies local and accessibility functional with a keyboard and small screen.

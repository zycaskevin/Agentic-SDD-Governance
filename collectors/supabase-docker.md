# Supabase and Docker Collectors

## Supabase (`supabase-log`)

Default to the local development stack. Record the command, local project reference, migration snapshot, API status, and narrow service log window.

```bash
mkdir -p <DEP>/private/raw
supabase_status=0
supabase status > <DEP>/private/raw/supabase-status.txt 2>&1 || supabase_status=$?
test "$supabase_status" -eq 0
evidence collect <DEP> --collector supabase-log --input <DEP>/private/raw/supabase-status.txt
supabase functions serve <name> --debug > <DEP>/private/raw/supabase-function.log 2>&1 &
serve_pid=$!
```

Run the bounded reproduction while the local server is active. Then interrupt that exact process, wait for it to exit, preserve its exit status, confirm that the log is non-empty, and only then import it:

```bash
kill -INT "$serve_pid"
serve_status=0
wait "$serve_pid" || serve_status=$?
test "$serve_status" -eq 0 -o "$serve_status" -eq 130
test -s <DEP>/private/raw/supabase-function.log
evidence collect <DEP> --collector supabase-log --input <DEP>/private/raw/supabase-function.log
```

Fail closed when a command may target production. Do not apply, repair, reset, or replay a production migration as evidence collection. Do not export tables or auth records. Remove JWTs, service-role keys, emails, user IDs, database URLs, and webhook signatures.

## Docker (`docker-log`)

Use explicit container/service names and a bounded time window:

```bash
mkdir -p <DEP>/private/raw
docker logs --since 10m <test-container> > <DEP>/private/raw/docker-failure.log 2>&1
docker_status=$?
test "$docker_status" -eq 0
test -s <DEP>/private/raw/docker-failure.log
evidence collect <DEP> --collector docker-log --input <DEP>/private/raw/docker-failure.log
```

Do not collect every container or environment dump. `docker inspect` may reveal environment secrets; prefer a manually written configuration summary unless exact non-secret metadata is required.

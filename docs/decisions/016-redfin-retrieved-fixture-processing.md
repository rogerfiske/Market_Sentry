# Decision 016: Redfin Retrieved Fixture Processing Pipeline

**Date:** 2026-05-07
**Status:** Accepted
**Milestone:** 17

## Context

Milestone 16 added the ability to retrieve Redfin HTML pages via HTTP and save them as local fixtures. This decision addresses how those saved fixtures flow into the existing candidate pipeline.

## Decisions

### Why Retrieval Saves Fixtures First

Retrieved HTML is saved as local fixture files rather than being parsed inline during retrieval because:

1. **Auditability**: The raw HTML is preserved for review and debugging.
2. **Reprocessing**: Fixtures can be re-parsed if parsers are improved.
3. **Separation of concerns**: Retrieval (network) and parsing (local) are independent operations.
4. **Error isolation**: A retrieval failure does not affect parsing; a parse failure does not lose retrieved data.
5. **Consistency**: The same parsers work for both manually saved and live-retrieved pages.

### Why Parsing Is a Separate Step

Making parsing a separate CLI command rather than automatic ensures:

1. **Human oversight**: The user decides when to process fixtures.
2. **Batch processing**: Multiple fixtures can be processed at once.
3. **Idempotency**: Content-hash-based skip logic prevents redundant processing.
4. **Debugging**: Parse errors can be investigated without re-retrieving.

### Why Direct Database Mutation from HTTP Response Is Avoided

Inserting candidates directly from HTTP response data (bypassing fixture files) would:

1. Lose the raw HTML for re-parsing if parsers improve.
2. Mix network and database concerns in one operation.
3. Make testing harder (would need to mock both HTTP and DB).
4. Prevent the user from inspecting the raw data before it enters the pipeline.

### Why Manifest-Based Idempotency Is Used

The processing manifest CSV tracks processed fixtures by content hash because:

1. **Content-based**: If the file hasn't changed, it's already processed.
2. **Append-only**: No data is lost from the manifest.
3. **Force-reprocess**: The user can override with `--force-reprocess`.
4. **Lightweight**: A CSV file is simpler than adding processing state to the database.
5. **No file deletion**: Fixture files are never modified or removed.

### Why Capture Queue Integration Is Useful

When a fixture is processed successfully and its `source_url` matches a pending fixture capture queue request, marking it as captured:

1. Keeps the queue accurate without manual intervention.
2. Closes the loop between "retrieval blocked -> manual save -> processing."
3. Only marks successfully processed fixtures (not errors).

## Consequences

- Processing is always a separate, explicit step after retrieval or manual saving.
- The same pipeline works for manually saved and live-retrieved fixtures.
- Content-hash-based idempotency prevents redundant work.
- The fixture capture queue stays in sync with actual processing.
- Future improvements to parsers can reprocess existing fixtures with `--force-reprocess`.

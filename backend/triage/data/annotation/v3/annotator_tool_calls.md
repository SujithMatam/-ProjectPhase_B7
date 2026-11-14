**Annotator tool calls (self-reported; the transcript is not kept).** 1. Read
`LABELLING_GUIDELINE.md` in full. 2. Read `annotation/v3/blind_items.tsv` in full. 3. Shell: wrote
`second_labels.tsv` from a hand-typed string of R/Y/G letters (the shell only numbered them into
ids); the string was mistyped and gave 390 lines, so the file was overwritten. 4. Shell: the same
command with the letters re-entered in blocks of ten (363 ids), then `cut | sort | uniq -c` for the
counts. 5. Two spot-check greps of about 25 ids to confirm labels sat on the right ids. It reports
no other file reads and no git. Reported counts: GREEN 203, YELLOW 104, RED 56.

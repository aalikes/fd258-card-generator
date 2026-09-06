---
name: international-instruction-submission
description: Draft or send the international FD-258 fingerprint card submission instructions email to a Provn/MetroPrints client (mail-in FBI CJIS background check process). Use when Shah asks to send/draft "international submission instructions", "FD-258 instructions", or similar to a client by name/email.
---

# International Instruction Submission (FD-258 / FBI mail-in)

Sends the standard 7-step instruction email that walks an international (or remote) FBI
Identity History Summary client through printing, fingerprinting, mailing, and confirming
their FD-258 card packet, mirroring the "FBI Background Check — Printing & Mailing Packet
(SOP)" playbook in the MP - Playbooks Notion database (step: "Technician emails the client
with next-step instructions").

A matching Gmail template named **"International Submission Instructions — FBI Background
Check (FD-258)"** is saved on shah@getproven.us (Settings → Advanced → Templates must stay
enabled). This skill reproduces that template's body exactly and is the source of truth if
the two ever drift — update both together.

## When to use

Trigger on requests like:
- "Send [client] the international submission instructions"
- "Draft the FD-258 instructions email for [name/email]"
- "Email [client] their FBI background check mailing steps"

## What to collect before sending

1. **Client first name** — replaces the `My first name` placeholder in the greeting.
2. **Client email address.**
3. **Attachments** — Gmail templates do NOT carry attachments, so always attach fresh:
   - The blank/fillable FD-258 card PDF (ask Shah for the current file, or use the one most
     recently referenced in this conversation / uploads).
   - The FBI EDO request-confirmation page (client-specific — ask Shah for it; do not reuse
     another client's confirmation page).

## Email content (exact body — bold as shown)

```
Hello [First Name],

The FD-258 fillable cards and FBI request-confirmation page are attached to this email.

Step 1. Print the attached FD-258 fillable cards and confirmation page.

Step 2. Have black fingerprint ink ready to use on the FD-258 cards.

Step 3. Schedule a Zoom meeting and have the FD-258 cards ready. Have extra loose-leaf paper ready for testing before completing the final cards.
To schedule the Zoom meeting, use the Meetings link below or call (718) 501-1604.
[Meetings -> https://fantastical.app/aalikes/meeting]

Step 4. Scan the completed FD-258 fingerprint cards and email the scans to shah@getproven.us.

Step 5. Place both completed FD-258 cards and the printed confirmation page in the mailing envelope.

Step 6. Mail the packet to:
FBI CJIS Division, ATTN: ELECTRONIC SUMMARY REQUEST, 1000 Custer Hollow Road, Clarksburg, WV 26306
Keep the mailing receipt and tracking number.

Step 7. Email the scanned FD-258 cards and tracking number to shah@getproven.us.
```

Subject line: `International Submission Instructions — FBI Background Check (FD-258)`

Formatting rules:
- "Step 1." through "Step 7." are **bold**.
- "Meetings" is a hyperlink to `https://fantastical.app/aalikes/meeting`.
- Both instances of `shah@getproven.us` are `mailto:` hyperlinks.
- Keep the FBI CJIS mailing address on its own line, verbatim (this exact address is also
  the single source of truth used elsewhere in the MP - Playbooks SOP — never alter it
  without updating that page too).

## How to send

1. Build the HTML body above, substituting the client's first name for `[First Name]`.
2. Use the Gmail MCP tools (`mcp__Gmail__create_draft` to stage it for Shah's review, or
   `mcp__Gmail__send_message` only if Shah explicitly says to send immediately) with:
   - `to`: client email
   - `subject`: the subject line above
   - HTML body as shown
   - attachments: the FD-258 fillable card PDF + that client's FBI confirmation page
3. Default to creating a **draft**, not sending — confirm with Shah before it goes out,
   since each client's confirmation-page attachment must be verified as theirs.
4. After sending/drafting, note in Notion (MP - Playbooks → the relevant client's MP -
   Activities row) that the instructions email was sent, per the SOP's back-office logging
   step.

## Keeping this in sync

This skill, the Gmail template, and the Notion SOP page
("FBI Background Check — Printing & Mailing Packet (SOP)", MP - Playbooks database) all
carry the same instruction text. If Shah changes wording, mailing address, phone number, or
links, update all three:
1. Gmail template (Settings → Advanced → Templates, or via a compose → More options →
   Templates → Save draft as template, overwriting the existing one).
2. This skill file.
3. The Notion SOP page (and, via the existing Notion→Obsidian backup, the Obsidian vault
   copy will follow automatically).
---
name: international-instruction-submission
description: Draft or send the international FD-258 fingerprint card submission instructions email to a Provn/MetroPrints client (mail-in FBI CJIS background check process). Use when Shah asks to send/draft "international submission instructions", "FD-258 instructions", or similar to a client by name/email.
---

# International Instruction Submission (FD-258 / FBI mail-in)

Sends the standard 7-step instruction email that walks an international (or remote) FBI
Identity History Summary client through printing, fingerprinting, mailing, and confirming
their FD-258 card packet, mirroring the "FBI Background Check — Printing & Mailing Packet
(SOP)" playbook in the MP - Playbooks Notion database (step: "Technician emails the client
with next-step instructions").

A matching Gmail template named **"International Submission Instructions — FBI Background
Check (FD-258)"** is saved on shah@getproven.us (Settings → Advanced → Templates must stay
enabled). This skill reproduces that template's body exactly and is the source of truth if
the two ever drift — update both together.

## When to use

Trigger on requests like:
- "Send [client] the international submission instructions"
- "Draft the FD-258 instructions email for [name/email]"
- "Email [client] their FBI background check mailing steps"

## What to collect before sending

1. **Client first name** — replaces the `My first name` placeholder in the greeting.
2. **Client email address.**
3. **Attachments** — Gmail templates do NOT carry attachments, so always attach fresh:
   - The blank/fillable FD-258 card PDF (ask Shah for the current file, or use the one most
     recently referenced in this conversation / uploads).
   - The FBI EDO request-confirmation page (client-specific — ask Shah for it; do not reuse
     another client's confirmation page).

## Email content (exact body — bold as shown)

```
Hello [First Name],

The FD-258 fillable cards and FBI request-confirmation page are attached to this email.

Step 1. Print the attached FD-258 fillable cards and confirmation page.

Step 2. Have black fingerprint ink ready to use on the FD-258 cards.

Step 3. Schedule a Zoom meeting and have the FD-258 cards ready. Have extra loose-leaf paper ready for testing before completing the final cards.
To schedule the Zoom meeting, use the Meetings link below or call (718) 501-1604.
[Meetings -> https://fantastical.app/aalikes/meeting]

Step 4. Scan the completed FD-258 fingerprint cards and email the scans to shah@getproven.us.

Step 5. Place both completed FD-258 cards and the printed confirmation page in the mailing envelope.

Step 6. Mail the packet to:
FBI CJIS Division, ATTN: ELECTRONIC SUMMARY REQUEST, 1000 Custer Hollow Road, Clarksburg, WV 26306
Keep the mailing receipt and tracking number.

Step 7. Email the scanned FD-258 cards and tracking number to shah@getproven.us.
```

Subject line: `International Submission Instructions — FBI Background Check (FD-258)`

Formatting rules:
- "Step 1." through "Step 7." are **bold**.
- "Meetings" is a hyperlink to `https://fantastical.app/aalikes/meeting`.
- Both instances of `shah@getproven.us` are `mailto:` hyperlinks.
- Keep the FBI CJIS mailing address on its own line, verbatim (this exact address is also
  the single source of truth used elsewhere in the MP - Playbooks SOP — never alter it
  without updating that page too).

## How to send

1. Build the HTML body above, substituting the client's first name for `[First Name]`.
2. Use the Gmail MCP tools (`mcp__Gmail__create_draft` to stage it for Shah's review, or
   `mcp__Gmail__send_message` only if Shah explicitly says to send immediately) with:
   - `to`: client email
   - `subject`: the subject line above
   - HTML body as shown
   - attachments: the FD-258 fillable card PDF + that client's FBI confirmation page
3. Default to creating a **draft**, not sending — confirm with Shah before it goes out,
   since each client's confirmation-page attachment must be verified as theirs.
4. After sending/drafting, note in Notion (MP - Playbooks → the relevant client's MP -
   Activities row) that the instructions email was sent, per the SOP's back-office logging
   step.

## Keeping this in sync

This skill, the Gmail template, and the Notion SOP page
("FBI Background Check — Printing & Mailing Packet (SOP)", MP - Playbooks database) all
carry the same instruction text. If Shah changes wording, mailing address, phone number, or
links, update all three:
1. Gmail template (Settings → Advanced → Templates, or via a compose → More options →
   Templates → Save draft as template, overwriting the existing one).
2. This skill file.
3. The Notion SOP page (and, via the existing Notion→Obsidian backup, the Obsidian vault
   copy will follow automatically).
---
name: international-instruction-submission
description: Draft or send the international FD-258 fingerprint card submission instructions email to a Provn/MetroPrints client (mail-in FBI CJIS background check process). Use when Shah asks to send/draft "international submission instructions", "FD-258 instructions", or similar to a client by name/email.
---

# International Instruction Submission (FD-258 / FBI mail-in)

Sends the standard 7-step instruction email that walks an international (or remote) FBI
Identity History Summary client through printing, fingerprinting, mailing, and confirming
their FD-258 card packet, mirroring the "FBI Background Check — Printing & Mailing Packet
(SOP)" playbook in the MP - Playbooks Notion database (step: "Technician emails the client
with next-step instructions").

A matching Gmail template named **"International Submission Instructions — FBI Background
Check (FD-258)"** is saved on shah@getproven.us (Settings → Advanced → Templates must stay
enabled). This skill reproduces that template's body exactly and is the source of truth if
the two ever drift — update both together.

## When to use

Trigger on requests like:
- "Send [client] the international submission instructions"
- "Draft the FD-258 instructions email for [name/email]"
- "Email [client] their FBI background check mailing steps"

## What to collect before sending

1. **Client first name** — replaces the `My first name` placeholder in the greeting.
2. **Client email address.**
3. **Attachments** — Gmail templates do NOT carry attachments, so always attach fresh:
   - The blank/fillable FD-258 card PDF (ask Shah for the current file, or use the one most
     recently referenced in this conversation / uploads).
   - The FBI EDO request-confirmation page (client-specific — ask Shah for it; do not reuse
     another client's confirmation page).

## Email content (exact body — bold as shown)

```
Hello [First Name],

The FD-258 fillable cards and FBI request-confirmation page are attached to this email.

Step 1. Print the attached FD-258 fillable cards and confirmation page.

Step 2. Have black fingerprint ink ready to use on the FD-258 cards.

Step 3. Schedule a Zoom meeting and have the FD-258 cards ready. Have extra loose-leaf paper ready for testing before completing the final cards.
To schedule the Zoom meeting, use the Meetings link below or call (718) 501-1604.
[Meetings -> https://fantastical.app/aalikes/meeting]

Step 4. Scan the completed FD-258 fingerprint cards and email the scans to shah@getproven.us.

Step 5. Place both completed FD-258 cards and the printed confirmation page in the mailing envelope.

Step 6. Mail the packet to:
FBI CJIS Division, ATTN: ELECTRONIC SUMMARY REQUEST, 1000 Custer Hollow Road, Clarksburg, WV 26306
Keep the mailing receipt and tracking number.

Step 7. Email the scanned FD-258 cards and tracking number to shah@getproven.us.
```

Subject line: `International Submission Instructions — FBI Background Check (FD-258)`

Formatting rules:
- "Step 1." through "Step 7." are **bold**.
- "Meetings" is a hyperlink to `https://fantastical.app/aalikes/meeting`.
- Both instances of `shah@getproven.us` are `mailto:` hyperlinks.
- Keep the FBI CJIS mailing address on its own line, verbatim (this exact address is also
  the single source of truth used elsewhere in the MP - Playbooks SOP — never alter it
  without updating that page too).

## How to send

1. Build the HTML body above, substituting the client's first name for `[First Name]`.
2. Use the Gmail MCP tools (`mcp__Gmail__create_draft` to stage it for Shah's review, or
   `mcp__Gmail__send_message` only if Shah explicitly says to send immediately) with:
   - `to`: client email
   - `subject`: the subject line above
   - HTML body as shown
   - attachments: the FD-258 fillable card PDF + that client's FBI confirmation page
3. Default to creating a **draft**, not sending — confirm with Shah before it goes out,
   since each client's confirmation-page attachment must be verified as theirs.
4. After sending/drafting, note in Notion (MP - Playbooks → the relevant client's MP -
   Activities row) that the instructions email was sent, per the SOP's back-office logging
   step.

## Keeping this in sync

This skill, the Gmail template, and the Notion SOP page
("FBI Background Check — Printing & Mailing Packet (SOP)", MP - Playbooks database) all
carry the same instruction text. If Shah changes wording, mailing address, phone number, or
links, update all three:
1. Gmail template (Settings → Advanced → Templates, or via a compose → More options →
   Templates → Save draft as template, overwriting the existing one).
2. This skill file.
3. The Notion SOP page (and, via the existing Notion→Obsidian backup, the Obsidian vault
   copy will follow automatically).

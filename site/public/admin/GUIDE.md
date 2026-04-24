# Iris CMS — Editor Guide

*Short guide for reviewing and refining monthly editions.*

## What this is

Iris produces a monthly report on the EU chemical industry. The pipeline
drafts the text automatically from Eurostat and Comext data. This CMS is
where you (the editor) refine the wording before the edition is considered
final.

Your edits are saved as git commits and go live on `iris.cefic.org`
within about two minutes.

## How to log in

1. Open **https://iris.cefic.org/admin/** in your browser.
2. You will be redirected to the Cefic single sign-on page (Entra ID).
3. Sign in with your Cefic account.
4. The editor opens on the list of editions.

If you see "Access denied", your email is not on the allowlist. Contact
Jonathan.

## What you can edit

Each edition has these fields:

| Field | Edit? |
|-------|-------|
| Month | ⛔ Do not edit — drives the URL and file name |
| Publication date | ⛔ Do not edit |
| Pipeline version | ⛔ Do not edit |
| Reviewed | ✅ Tick when your review is complete (see below) |
| Body | ✅ This is where you refine the wording |

## The rules for editing the body

### ✅ Do
- Rephrase sentences, fix typos, tighten awkward wording.
- Replace one adjective with a better one.
- Reorder clauses for clarity.

### ⛔ Never
- **Change a number.** All figures (`42.1%`, `€34.5 bn`, `79.3 on the 2021
  index`) come from Eurostat/Comext and must match the charts. If a number
  looks wrong, contact Jonathan — do not edit it yourself.
- **Touch the chart tags.** Lines like:

  ```html
  <img src="/charts/2026-02/output_index.svg" alt="output_index" />
  ```

  These are the dashboard's chart references. Even whitespace inside the
  tag can break the render.
- **Remove the `---` separators.** Three dashes on their own line mark the
  boundary between sections in the dashboard. Removing one merges two
  sections visually.

### 🤷 If you are unsure
Ask Jonathan before saving. A save commits directly to the site.

## Marking an edition as reviewed

1. Edit the body as needed.
2. Tick the **Reviewed** checkbox.
3. Click **Save**.

Once Reviewed is `true`, the pipeline will **refuse to regenerate this
edition** on the next monthly run. Your edits are safe until you (or
Jonathan) untick the box.

If you later want the pipeline to refresh the data while keeping most of
your prose, untick Reviewed, save, then ping Jonathan to re-run the
pipeline.

## What happens after Save

1. A commit is created on the `kendrick7410/iris` GitHub repo with your
   edit. The commit message names the edition you changed.
2. Azure rebuilds the site (takes ~90 seconds).
3. The change is live on `iris.cefic.org`.

Cefic-side audit trail of who did what is in Azure (your Cefic login is
logged server-side). Every save passes through Cefic SSO so only
allowlisted editors can reach the CMS.

## If something goes wrong

- **"Save" button does nothing** — refresh the page; if still broken,
  contact Jonathan.
- **Edit looks cut off** — do not save. Close the tab, reopen. Report to
  Jonathan.
- **CMS shows a "Sign in with GitHub" screen** — this means the SSO bridge
  broke. Do not try to sign in with GitHub. Contact Jonathan — the CMS is
  in a broken state.
- **Wrong number in the text** — do NOT edit it. Report to Jonathan so the
  data source can be fixed and the pipeline re-run.

## Contact

Jonathan Mead — `jme@cefic.be`

---

*Technical note for future editors: this CMS currently shows the whole
edition as one editable block. A sectioned view (one field per section) is
planned for a future upgrade. Until then, be careful with `---` separators
and `<img/>` tags.*

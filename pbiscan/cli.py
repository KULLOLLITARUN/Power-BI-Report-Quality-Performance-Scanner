"""pbiscan CLI — full pipeline orchestration.

Usage:
    pbiscan scan ./Sales.pbip
    pbiscan scan ./Sales.pbip --config rules.config.json --out report.html
    pbiscan scan ./Sales.pbip --verbose
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from pbiscan import __version__
from pbiscan.engine.scoring import ConfigError
from pbiscan.extraction.pbip_reader import PBIScanError
from pbiscan.service import ScanService, resolve_config

# Default config path (relative to CWD)
DEFAULT_CONFIG = "rules.config.json"

# Severity display order for CLI output
_SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "WARNING", "ADVISORY", "LOW"]
_SEVERITY_COLOURS = {
    "CRITICAL": "\033[91m",   # bright red
    "HIGH":     "\033[31m",   # red
    "MEDIUM":   "\033[33m",   # yellow
    "WARNING":  "\033[93m",   # bright yellow
    "ADVISORY": "\033[34m",   # blue
    "LOW":      "\033[37m",   # grey
}
_RESET = "\033[0m"
_BOLD  = "\033[1m"
_DIM   = "\033[2m"
_GREEN = "\033[32m"
_CYAN  = "\033[36m"
_RED   = "\033[31m"


def _colour(text: str, code: str) -> str:
    """Apply ANSI colour code if stdout is a terminal."""
    if sys.stdout.isatty():
        return f"{code}{text}{_RESET}"
    return text


def _score_colour(score: float) -> str:
    if score >= 80:
        return "\033[32m"   # green
    if score >= 60:
        return "\033[33m"   # yellow
    return "\033[31m"        # red


@click.group()
@click.version_option(__version__, prog_name="pbiscan")
def main() -> None:
    """pbiscan — Power BI Report Quality & Performance Scanner.

    Scans a PBIP project and produces an evidence-based quality audit.
    """


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--config", "-c",
    type=click.Path(),
    default=None,
    help="Path to rules.config.json. Defaults to ./rules.config.json.",
)
@click.option(
    "--out", "-o",
    type=click.Path(),
    default=None,
    help="Output path for HTML report (e.g. report.html). If omitted, CLI summary only.",
)
@click.option(
    "--format", "-f",
    "output_format",
    type=click.Choice(["html", "json", "sarif", "junit"], case_sensitive=False),
    default="html",
    show_default=True,
    help="Output format when --out is specified.",
)
@click.option(
    "--fail-under",
    type=float,
    default=None,
    help="Exit with code 1 if overall score is below this threshold (CI/CD gate).",
)
@click.option(
    "--fail-on",
    type=click.Choice(["CRITICAL", "HIGH", "MEDIUM", "WARNING", "ADVISORY", "LOW"], case_sensitive=False),
    default=None,
    help="Exit with code 1 if any unsuppressed issue with this severity or higher is found (CI/CD gate).",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose/debug logging.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress all output except errors.")
def scan(
    path: str,
    config: str | None,
    out: str | None,
    output_format: str,
    fail_under: float | None,
    fail_on: str | None,
    verbose: bool,
    quiet: bool,
) -> None:
    """Scan a PBIP project directory and report quality findings.

    PATH is the path to the .pbip project directory to scan.
    """
    # Configure logging
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s  %(message)s", stream=sys.stderr)
    elif quiet:
        logging.basicConfig(level=logging.ERROR, stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(message)s", stream=sys.stderr)

    logger = logging.getLogger(__name__)

    # Banner
    if not quiet:
        click.echo(f"\n{_colour('pbiscan', _BOLD)} {_colour(f'v{__version__}', _DIM)} - Power BI Report Quality & Performance Scanner\n")
        click.echo(f"  Scanning: {_colour(path, _CYAN)}")

    # Execute Canonical Scan Pipeline
    try:
        result = ScanService.execute_scan(
            project_path=path,
            config_path=config,
        )
    except ConfigError as exc:
        click.echo(f"[ERROR] Config error: {exc}", err=True)
        sys.exit(1)
    except PBIScanError as exc:
        click.echo(f"[ERROR] Extraction failed: {exc}", err=True)
        sys.exit(2)
    except Exception as exc:
        click.echo(f"[ERROR] Scan failed: {exc}", err=True)
        sys.exit(2)

    report = result.report
    issues = result.issues
    scores = result.scores
    overall = result.overall_score
    cat_scores = result.category_scores

    if not quiet:
        for w in result.warnings:
            click.echo(f"  {_colour('[WARN]', _BOLD)}  {w}")

        click.echo(
            f"  Tables: {_colour(str(len(report.model.tables)), _CYAN)}  "
            f"Relationships: {_colour(str(len(report.model.relationships)), _CYAN)}  "
            f"Measures: {_colour(str(len(report.dax.measures)), _CYAN)}  "
            f"Pages: {_colour(str(len(report.report.pages)), _CYAN)}"
        )
        click.echo("")
        score_col = _score_colour(overall)
        score_disp = f"{int(overall)}" if overall == int(overall) else f"{overall:.1f}"
        click.echo(f"  {_colour('Overall Health:', _BOLD)}  {_colour(score_disp, score_col)}")
        click.echo("")
        m_s = cat_scores.get('model', 100)
        d_s = cat_scores.get('dax', 100)
        r_s = cat_scores.get('report', 100)
        m_disp = f"{int(m_s)}" if m_s == int(m_s) else f"{m_s:.1f}"
        d_disp = f"{int(d_s)}" if d_s == int(d_s) else f"{d_s:.1f}"
        r_disp = f"{int(r_s)}" if r_s == int(r_s) else f"{r_s:.1f}"
        click.echo(
            f"  Model: {_colour(m_disp, _score_colour(m_s))}  "
            f"DAX: {_colour(d_disp, _score_colour(d_s))}  "
            f"Report: {_colour(r_disp, _score_colour(r_s))}"
        )
        click.echo("")

        if issues:
            click.echo(f"  Findings ({len(issues)}):")
            sorted_issues = sorted(issues, key=lambda i: _SEVERITY_ORDER.index(i.severity) if i.severity in _SEVERITY_ORDER else 99)
            for issue in sorted_issues:
                sev_col = _SEVERITY_COLOURS.get(issue.severity, "")
                sev_str = _colour(f"  {issue.severity:<10}", sev_col)
                # ASCII-safe location for Windows consoles (preserve arrow direction)
                loc_raw = issue.location or ""
                loc_clean = loc_raw.replace("↔", "<->").replace("→", "->").replace("←", "<-")
                loc_ascii = loc_clean.encode("ascii", "replace").decode("ascii")
                loc_str = f"  {_colour(loc_ascii, _DIM)}" if loc_ascii else ""
                supp_str = f"  {_colour('(suppressed)', _DIM)}" if issue.suppressed else ""
                click.echo(f"  {sev_str}{issue.rule_id}{loc_str}{supp_str}")
        else:
            click.echo(f"  {_colour('[PASS] No findings', _GREEN)} - this report looks clean!")

    # Write output file if requested
    if out:
        output_path = Path(out)
        try:
            fmt_lower = output_format.lower()
            if fmt_lower == "json":
                output_path.write_text(result.to_json(), encoding="utf-8")
            elif fmt_lower == "sarif":
                output_path.write_text(result.to_sarif(), encoding="utf-8")
            elif fmt_lower == "junit":
                output_path.write_text(result.to_junit(), encoding="utf-8")
            else:
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                output_path.write_text(result.to_html(timestamp=timestamp), encoding="utf-8")

            if not quiet:
                click.echo(f"\n  Report saved: {_colour(str(output_path), _GREEN)}")
        except Exception as exc:
            click.echo(f"[ERROR] Failed to write report: {exc}", err=True)
            sys.exit(1)
    elif not quiet:
        click.echo("")

    # Step 8 — CI/CD threshold and quality gates
    gate_failed = False

    if fail_under is not None and overall < fail_under:
        if not quiet:
            click.echo(
                f"  {_colour('FAIL:', _RED)} Overall score {overall:.1f} is below threshold {fail_under}\n",
                err=True,
            )
        gate_failed = True

    if fail_on is not None:
        fail_on_upper = fail_on.upper()
        if fail_on_upper in _SEVERITY_ORDER:
            threshold_idx = _SEVERITY_ORDER.index(fail_on_upper)
            triggering = [
                i for i in issues
                if not i.suppressed and i.severity in _SEVERITY_ORDER and _SEVERITY_ORDER.index(i.severity) <= threshold_idx
            ]
            if triggering:
                if not quiet:
                    click.echo(
                        f"  {_colour('FAIL:', _RED)} Found {len(triggering)} unsuppressed issue(s) with severity >= {fail_on_upper}\n",
                        err=True,
                    )
                gate_failed = True

    if gate_failed:
        sys.exit(1)


@main.command()
@click.argument("path", type=click.Path(exists=True), required=False, default=None)
@click.option("--port", "-p", default=8000, help="Port to bind the Studio server.")
@click.option("--host", "-h", default="127.0.0.1", help="Host address to bind.")
@click.option("--no-browser", is_flag=True, help="Do not automatically open browser.")
def studio(path: str | None, port: int, host: str, no_browser: bool) -> None:
    """Launch pbiscan Studio interactive developer web UI."""
    import webbrowser
    import uvicorn

    url = f"http://{host}:{port}"
    if path:
        url += f"?path={Path(path).resolve()}"

    click.echo(f"\n{_colour('pbiscan Studio', _BOLD)} - Starting visual workspace...")
    click.echo(f"  Local Server: {_colour(url, _CYAN)}")
    click.echo(f"  Press {_colour('Ctrl+C', _BOLD)} to stop.\n")

    if not no_browser:
        webbrowser.open(url)

    uvicorn.run("pbiscan.server:app", host=host, port=port, log_level="warning")


@main.command()
@click.argument("baseline", type=click.Path())
@click.argument("current", type=click.Path())
@click.option(
    "--config", "-c",
    type=click.Path(),
    default=None,
    help="Path to rules.config.json for PBIP scans.",
)
@click.option(
    "--format", "-f",
    "output_format",
    type=click.Choice(["console", "json", "markdown"], case_sensitive=False),
    default="console",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--out", "-o",
    type=click.Path(),
    default=None,
    help="Output file path (e.g. diff.json, pr_comment.md). If omitted, prints to stdout.",
)
@click.option(
    "--fail-on-regression",
    is_flag=True,
    help="Exit with code 1 if overall health score regresses (delta < 0).",
)
@click.option(
    "--max-score-drop",
    type=float,
    default=None,
    help="Exit with code 1 if overall score drop exceeds this threshold (e.g. 3.0).",
)
@click.option(
    "--fail-on-new",
    type=click.Choice(["CRITICAL", "HIGH", "MEDIUM", "WARNING", "ADVISORY", "LOW"], case_sensitive=False),
    default=None,
    help="Exit with code 1 if any newly introduced finding has this severity or higher.",
)
@click.option(
    "--fail-on-category-regression",
    type=click.Choice(["model", "dax", "report"], case_sensitive=False),
    default=None,
    help="Exit with code 1 if the specified category score regresses.",
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    help="Suppress stdout console output (useful in CI scripts).",
)
def diff(
    baseline: str,
    current: str,
    config: Optional[str],
    output_format: str,
    out: Optional[str],
    fail_on_regression: bool,
    max_score_drop: Optional[float],
    fail_on_new: Optional[str],
    fail_on_category_regression: Optional[str],
    quiet: bool,
) -> None:
    """Compare two scans (PBIP projects or JSON scan artifacts) and track drift."""
    from pbiscan.diff import DiffService, QualityGatePolicy
    from pbiscan.render.diff_console import DiffConsoleRenderer
    from pbiscan.render.diff_markdown import DiffMarkdownRenderer

    base_path = Path(baseline)
    curr_path = Path(current)

    if not base_path.exists():
        click.echo(f"[ERROR] Baseline path does not exist: {baseline}", err=True)
        sys.exit(2)

    if not curr_path.exists():
        click.echo(f"[ERROR] Current path does not exist: {current}", err=True)
        sys.exit(2)

    policy = QualityGatePolicy(
        fail_on_regression=fail_on_regression,
        max_score_drop=max_score_drop,
        fail_on_new=fail_on_new,
        fail_on_category_regression=fail_on_category_regression,
    )

    try:
        diff_res = DiffService.compare(
            baseline=base_path,
            current=curr_path,
            policy=policy,
            config_path=config,
        )
    except Exception as exc:
        click.echo(f"[ERROR] Diff execution failed: {exc}", err=True)
        sys.exit(2)

    # Render output
    fmt_lower = output_format.lower()
    if fmt_lower == "json":
        rendered = diff_res.to_json()
    elif fmt_lower == "markdown":
        rendered = DiffMarkdownRenderer().render(diff_res)
    else:
        rendered = DiffConsoleRenderer().render(diff_res)

    if out:
        try:
            Path(out).write_text(rendered, encoding="utf-8")
            if not quiet:
                click.echo(f"\n  Diff report saved: {_colour(str(out), _GREEN)}")
        except Exception as exc:
            click.echo(f"[ERROR] Failed to write diff report: {exc}", err=True)
            sys.exit(2)
    elif not quiet:
        try:
            click.echo(rendered)
        except UnicodeEncodeError:
            encoding = sys.stdout.encoding or "utf-8"
            safe_text = rendered.encode(encoding, errors="replace").decode(encoding)
            click.echo(safe_text)

    # Quality gate decision exit code
    if not diff_res.verdict.passed:
        sys.exit(1)

    sys.exit(0)


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--apply",
    is_flag=True,
    help="Apply validated remediation patches to disk (default is dry-run plan only).",
)
@click.option(
    "--interactive", "-i",
    is_flag=True,
    help="Interactively review and approve each remediation patch before applying.",
)
@click.option(
    "--patch-id", "-p",
    "patch_ids",
    multiple=True,
    type=str,
    help="Filter remediation to specific patch ID(s) (can specify multiple).",
)
@click.option(
    "--backup/--no-backup",
    default=True,
    show_default=True,
    help="Create timestamped .bak backup directory before modifying files.",
)
@click.option(
    "--rule", "-r",
    type=str,
    default=None,
    help="Filter remediation to a specific rule (e.g. MODEL_BIDIRECTIONAL).",
)
@click.option(
    "--config", "-c",
    type=click.Path(),
    default=None,
    help="Path to rules.config.json.",
)
@click.option(
    "--format", "-f",
    "output_format",
    type=click.Choice(["console", "json", "markdown"], case_sensitive=False),
    default="console",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--out", "-o",
    type=click.Path(),
    default=None,
    help="Output file path for remediation plan / manifest.",
)
@click.option(
    "--fail-on-remediation-available",
    is_flag=True,
    help="CI Governance: Exit with code 1 if safe actionable remediation is available.",
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    help="Suppress stdout console output.",
)
def fix(
    path: str,
    apply: bool,
    interactive: bool,
    patch_ids: tuple[str, ...],
    backup: bool,
    rule: Optional[str],
    config: Optional[str],
    output_format: str,
    out: Optional[str],
    fail_on_remediation_available: bool,
    quiet: bool,
) -> None:
    """Analyze, plan, review, and safely apply verified remediation patches to a PBIP model."""
    from pbiscan.remediation.engine import RemediationEngine
    from pbiscan.render.remediation_console import RemediationConsoleRenderer

    model_path = Path(path)
    if not model_path.exists():
        click.echo(f"[ERROR] Target path does not exist: {path}", err=True)
        sys.exit(2)

    try:
        # Phase 1: Baseline Scan
        scan_res = RemediationEngine.analyze(model_path, config_path=config)

        # Phase 2: Remediation Plan
        plan = RemediationEngine.plan(model_path, scan_res, rule_filter=rule)

        # Selective patch ID filter if specified
        if patch_ids:
            plan = plan.filter_by_patch_ids(patch_ids)
            if not plan.patches:
                click.echo(f"[WARN] No matching patches found for specified ID(s): {', '.join(patch_ids)}", err=True)

        # Phase 3: Sandbox Validation Loop
        validation = RemediationEngine.validate(plan, scan_res, config_path=config)
    except Exception as exc:
        click.echo(f"[ERROR] Remediation planning failed: {exc}", err=True)
        sys.exit(2)

    # Interactive Review Mode
    if interactive and plan.actionable_patches:
        approved_patch_ids: list[str] = []
        if not quiet:
            click.echo(RemediationConsoleRenderer.render_header(model_path.name, len(plan.actionable_patches), scan_res.overall_score))

        for idx, patch in enumerate(plan.actionable_patches, 1):
            if not quiet:
                click.echo(RemediationConsoleRenderer.render_patch_card(
                    patch, idx, len(plan.actionable_patches), validation.after_score, validation.before_score
                ))

            # Prompt user
            choice = click.prompt(
                f"  Apply patch {patch.patch_id}? [y=yes, n=no, a=all remaining, q=quit]",
                type=str,
                default="n",
                show_default=False,
            ).strip().lower()

            if choice in ("y", "yes"):
                approved_patch_ids.append(patch.patch_id)
            elif choice in ("a", "all"):
                approved_patch_ids.extend([p.patch_id for p in plan.actionable_patches[idx - 1:]])
                break
            elif choice in ("q", "quit"):
                click.echo("\nRemediation aborted by user.")
                sys.exit(0)

        if not approved_patch_ids:
            click.echo("\nNo patches approved. Exiting without modifying disk.")
            sys.exit(0)

        # Re-plan and re-validate only approved subset
        plan = plan.filter_by_patch_ids(approved_patch_ids)
        validation = RemediationEngine.validate(plan, scan_res, config_path=config)
        apply = True  # Proceed to apply the approved subset

    # Phase 4: Apply or Plan Preview
    if apply:
        if not plan.actionable_patches:
            if not quiet:
                click.echo(_colour("\nNo actionable patches to apply.", _GREEN))
            sys.exit(0)

        try:
            success, manifest = RemediationEngine.apply(
                plan=plan,
                validation_result=validation,
                backup=backup,
                config_path=config,
                original_scan=scan_res,
            )
        except Exception as exc:
            click.echo(f"[ERROR] Remediation apply failed with unexpected exception: {exc}", err=True)
            sys.exit(2)

        rendered = json.dumps(manifest.to_dict(), indent=2) if output_format.lower() == "json" else RemediationEngine.render_preview(plan, validation, output_format)

        if out:
            Path(out).write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
            if not quiet:
                click.echo(f"\n  Remediation manifest saved: {_colour(str(out), _GREEN)}")
        elif not quiet:
            if output_format.lower() == "console":
                click.echo(RemediationConsoleRenderer.render_summary(plan, validation))
            else:
                click.echo(rendered)

        if success:
            if not quiet:
                click.echo(_colour(f"\n✔ Successfully applied {len(plan.actionable_patches)} remediation patch(es).", _GREEN))
            sys.exit(0)
        else:
            if not quiet:
                click.echo(_colour("\n✖ Remediation rejected by validation or transactional rollback.", _RED), err=True)
            sys.exit(1)
    else:
        # Plan-only (Safe Default)
        if output_format.lower() == "json":
            out_data = {
                "model_path": str(plan.model_path),
                "validation": validation.to_dict(),
                "plan": plan.to_dict(),
            }
            rendered = json.dumps(out_data, indent=2)
        elif output_format.lower() == "markdown":
            rendered = RemediationEngine.render_preview(plan, validation, "markdown")
        else:
            # Console cards + summary
            header = RemediationConsoleRenderer.render_header(model_path.name, len(plan.actionable_patches), scan_res.overall_score)
            cards = [
                RemediationConsoleRenderer.render_patch_card(p, i, len(plan.actionable_patches), validation.after_score, validation.before_score)
                for i, p in enumerate(plan.actionable_patches, 1)
            ]
            summary = RemediationConsoleRenderer.render_summary(plan, validation)
            rendered = f"{header}\n" + "\n".join(cards) + f"\n{summary}"

        if out:
            Path(out).write_text(rendered, encoding="utf-8")
            if not quiet:
                click.echo(f"\n  Remediation plan saved: {_colour(str(out), _GREEN)}")
        elif not quiet:
            click.echo(rendered)

        if plan.actionable_patches:
            if fail_on_remediation_available:
                if not quiet:
                    click.echo(_colour("\n✖ CI Quality Gate: Safe remediation is available but unapplied (--fail-on-remediation-available).", _RED), err=True)
                sys.exit(1)
            # Exit 3: Plan-only / Review required
            sys.exit(3)
        else:
            # Exit 0: Clean model / No actionable findings
            sys.exit(0)


if __name__ == "__main__":
    main()




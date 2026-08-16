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
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.engine.issue import IssueGenerator
from pbiscan.engine.scoring import calculate_scores, load_config
from pbiscan.engine.suppressions import load_suppressions, apply_suppressions
from pbiscan.extraction.pbip_reader import PBIPReader, PBIScanError
from pbiscan.render.html_report import HtmlRenderer
from pbiscan.rules.dax import DAX_RULES
from pbiscan.rules.model import MODEL_RULES
from pbiscan.rules.report import REPORT_RULES

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


def _run_rules(report, config: dict) -> list:
    """Execute all 11 rules and return collected findings."""
    thresholds = config.get("thresholds", {})
    max_visuals = thresholds.get("maxVisualsPerPage", 15)
    max_slicers = thresholds.get("maxSlicersPerPage", 6)
    max_calc = thresholds.get("maxCalculatedColumnsPerTable", 4)

    # Load DAX suspicious patterns from config if present
    raw_patterns = config.get("dax_suspicious_patterns", [])
    dax_patterns = [(p["pattern"], p["description"]) for p in raw_patterns] or None

    findings = []
    for rule in MODEL_RULES:
        findings.extend(rule(report))

    findings.extend(DAX_RULES[0](report, patterns=dax_patterns))          # D001
    findings.extend(DAX_RULES[1](report, threshold=max_calc))              # D002
    findings.extend(DAX_RULES[2](report))                                  # D003
    findings.extend(DAX_RULES[3](report))                                  # D004

    findings.extend(REPORT_RULES[0](report, max_visuals=max_visuals))     # R001
    findings.extend(REPORT_RULES[1](report, max_slicers=max_slicers))     # R002

    return findings


def _find_default_config() -> str | None:
    """Find the default config file in CWD or package root."""
    local = Path(DEFAULT_CONFIG)
    if local.exists():
        return str(local)
    package_root = Path(__file__).parent.parent / DEFAULT_CONFIG
    if package_root.exists():
        return str(package_root)
    return None


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
    type=click.Choice(["html", "json"]),
    default="html",
    show_default=True,
    help="Output format when --out is specified.",
)
@click.option(
    "--fail-under",
    type=int,
    default=None,
    help="Exit with code 1 if overall score is below this threshold (CI/CD gate).",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose/debug logging.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress all output except errors.")
def scan(
    path: str,
    config: str | None,
    out: str | None,
    output_format: str,
    fail_under: int | None,
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

    # Resolve config
    config_path = config or _find_default_config()
    if not config_path:
        click.echo("WARNING: No rules.config.json found. Using built-in defaults.", err=True)
        cfg = {
            "weights": {"model": 0.35, "dax": 0.25, "report": 0.20, "security": 0.20},
            "deductions": {"CRITICAL": 15, "HIGH": 10, "MEDIUM": 5, "WARNING": 3, "ADVISORY": 1, "LOW": 2},
            "thresholds": {"maxVisualsPerPage": 15, "maxSlicersPerPage": 6, "maxCalculatedColumnsPerTable": 4},
        }
    else:
        try:
            cfg = load_config(config_path)
            if verbose:
                click.echo(f"  Config: {config_path}")
        except Exception as exc:
            click.echo(f"[ERROR] Config error: {exc}", err=True)
            sys.exit(1)

    # Step 1 — Extract
    try:
        reader = PBIPReader()
        if not quiet:
            click.echo(f"  Scanning: {_colour(path, _CYAN)}")
        raw = reader.read(path)
        for w in raw.warnings:
            if not quiet:
                click.echo(f"  {_colour('[WARN]', _BOLD)}  {w}")
    except PBIScanError as exc:
        click.echo(f"[ERROR] Extraction failed: {exc}", err=True)
        sys.exit(2)

    # Step 2 — Build canonical model
    try:
        builder = CanonicalBuilder()
        report = builder.build(raw)
    except PBIScanError as exc:
        click.echo(f"[ERROR] Canonical model build failed: {exc}", err=True)
        sys.exit(2)

    if not quiet:
        click.echo(
            f"  Tables: {_colour(str(len(report.model.tables)), _CYAN)}  "
            f"Relationships: {_colour(str(len(report.model.relationships)), _CYAN)}  "
            f"Measures: {_colour(str(len(report.dax.measures)), _CYAN)}  "
            f"Pages: {_colour(str(len(report.report.pages)), _CYAN)}"
        )

    # Step 3 — Run rules
    findings = _run_rules(report, cfg)
    logger.info("Found %d raw findings", len(findings))

    # Step 4 — Generate issues
    gen = IssueGenerator()
    issues = gen.generate(findings)

    # Step 4.5 — Apply suppressions
    suppressions = load_suppressions(path)
    issues = apply_suppressions(issues, suppressions)

    # Step 5 — Score
    scores = calculate_scores(issues, cfg)
    overall = scores["overall"]
    cat_scores = scores["category_scores"]

    # Step 6 — CLI output
    if not quiet:
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

    # Step 7 — Write output file
    if out:
        output_path = Path(out)
        try:
            if output_format == "json":
                data = {
                    "report_name": report.report_name,
                    "scan_timestamp": datetime.now(timezone.utc).isoformat(),
                    "scanner_version": __version__,
                    "scores": scores,
                    "findings": [
                        {
                            "rule_id": i.rule_id,
                            "category": i.category,
                            "severity": i.severity,
                            "title": i.title,
                            "issue": i.issue,
                            "evidence": i.evidence,
                            "impact": i.impact,
                            "recommendation": i.recommendation,
                            "confidence": i.confidence,
                            "location": i.location,
                            "suppressed": i.suppressed,
                            "suppression_reason": i.suppression_reason,
                        }
                        for i in issues
                    ],
                }
                output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            else:
                renderer = HtmlRenderer()
                html = renderer.render(
                    issues=issues,
                    scores=scores,
                    meta={
                        "report_name": report.report_name,
                        "scan_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                        "scanner_version": __version__,
                        "source_path": raw.source_path,
                    },
                )
                output_path.write_text(html, encoding="utf-8")

            if not quiet:
                click.echo(f"\n  Report written: {_colour(str(output_path), _CYAN)}\n")
        except Exception as exc:
            click.echo(f"✗ Render error: {exc}", err=True)
            sys.exit(1)
    elif not quiet:
        click.echo("")

    # Step 8 — CI/CD threshold gate
    if fail_under is not None and overall < fail_under:
        if not quiet:
            click.echo(
                f"  {_colour('FAIL:', _RED)} Overall score {overall:.1f} is below threshold {fail_under}\n",
                err=True,
            )
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


if __name__ == "__main__":
    main()



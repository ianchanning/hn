"""Cross-domain epistemic source registry for Hacker News URL classification.

Classifies external links across technical, scientific, legal, regulatory,
systems engineering, investigative journalism, and low-credibility/meme tiers:
- Tier 3 (Primary / Verifiable Artifacts): RFCs & web standards, arXiv/preprints,
  DOI & peer-reviewed journals, GitHub/GitLab/kernel commits|blobs|issues|PRs|releases,
  LWN, .gov/.mil, SEC EDGAR filings, court opinions, official advisories, PDFs, archives.
- Tier 2 (Investigative Press, Deep Tech Analysis & Code Repos): Reuters, AP, FT,
  Ars Technica, AnandTech, Quanta, .edu/.ac.uk, top-level code repositories.
- Tier 1 (General Reference): Wikipedia, general blogs, documentation homepages.
- Tier -1 (Low-Credibility / Joke / Snark Drops): YouTube gags, Google search links,
  meme/rumor subreddits, reaction image hosts, dictionary snark.
"""

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class SourceMatch:
    """Structured epistemic classification for a single external URL."""

    url: str
    host: str
    tier: int
    category: str
    is_primary: bool
    is_low_cred: bool


RFC_STANDARD_DOMAINS: tuple[str, ...] = (
    "rfc-editor.org",
    "datatracker.ietf.org",
    "tools.ietf.org",
    "ietf.org",
    "whatwg.org",
    "tc39.es",
    "peps.python.org",
    "unicode.org",
    "iso.org",
    "opencontainers.org",
    "khronos.org",
)

ARXIV_PREPRINT_DOMAINS: tuple[str, ...] = (
    "arxiv.org",
    "export.arxiv.org",
    "biorxiv.org",
    "medrxiv.org",
    "chemrxiv.org",
    "openreview.net",
    "eprint.iacr.org",
    "hal.science",
    "ssrn.com",
)

DOI_PEER_REVIEWED_DOMAINS: tuple[str, ...] = (
    "doi.org",
    "dx.doi.org",
    "dl.acm.org",
    "nature.com",
    "science.org",
    "pnas.org",
    "cell.com",
    "nejm.org",
    "thelancet.com",
    "bmj.com",
    "ncbi.nlm.nih.gov",
    "pubmed.ncbi.nlm.nih.gov",
    "iopscience.iop.org",
    "aps.org",
    "ams.org",
    "jmlr.org",
    "aclanthology.org",
    "usenix.org",
    "academic.oup.com",
    "cambridge.org",
    "springer.com",
    "link.springer.com",
    "ieeexplore.ieee.org",
)

LWN_DOMAINS: tuple[str, ...] = ("lwn.net",)

SEC_DOMAINS: tuple[str, ...] = ("sec.gov",)

GOV_AND_LEGAL_DOMAINS: tuple[str, ...] = (
    "congress.gov",
    "senate.gov",
    "house.gov",
    "justice.gov",
    "commerce.gov",
    "bis.doc.gov",
    "supremecourt.gov",
    "caselaw.findlaw.com",
    "law.cornell.edu",
    "courtlistener.com",
    "storage.courtlistener.com",
    "oyez.org",
    "cve.org",
    "nvd.nist.gov",
    "esa.int",
    "cern.ch",
    "minorplanetcenter.net",
)

KERNEL_AND_TRACKER_DOMAINS: tuple[str, ...] = (
    "git.kernel.org",
    "lore.kernel.org",
    "lkml.org",
    "bugs.chromium.org",
    "issuetracker.google.com",
    "bugzilla.mozilla.org",
    "bugs.python.org",
    "bugs.webkit.org",
    "bugs.llvm.org",
    "gcc.gnu.org",
    "raw.githubusercontent.com",
    "gist.github.com",
)

TIER3_TECHNICAL_AND_ARCHIVE_DOMAINS: tuple[str, ...] = (
    "nvidianews.nvidia.com",
    "images.nvidia.com",
    "culperresearch.com",
    "top500.org",
    "archive.ph",
    "archive.is",
    "web.archive.org",
    "docs.rs",
    "doc.rust-lang.org",
    "blog.rust-lang.org",
    "crates.io",
    "rustsec.org",
    "status.cloud.microsoft",
    "azure.status.microsoft",
    "health.aws.amazon.com",
    "status.cloud.google.com",
    "cloudflarestatus.com",
    "www.githubstatus.com",
    "githubstatus.com",
)

TIER2_INVESTIGATIVE_DOMAINS: tuple[str, ...] = (
    "reuters.com",
    "apnews.com",
    "ft.com",
    "wsj.com",
    "nytimes.com",
    "bloomberg.com",
    "politico.com",
    "axios.com",
    "cnn.com",
    "edition.cnn.com",
    "cnbc.com",
    "economist.com",
    "semafor.com",
    "arstechnica.com",
    "tomshardware.com",
    "anandtech.com",
    "semianalysis.com",
    "theregister.com",
    "wired.com",
    "quantamagazine.org",
    "spectrum.ieee.org",
    "ieee.org",
    "phys.org",
    "scientificamerican.com",
    "newscientist.com",
    "smithsonianmag.com",
    "spacenews.com",
    "skyandtelescope.org",
    "krebsonsecurity.com",
    "bleepingcomputer.com",
    "schneier.com",
    "danluu.com",
    "jvns.ca",
    "aphyr.com",
    "blog.cloudflare.com",
    "knowledge.insead.edu",
    "fortune.com",
    "nbcnews.com",
    "abcnews.com",
    "cbsnews.com",
)

CODE_FORGE_HOSTS: tuple[str, ...] = (
    "github.com",
    "gitlab.com",
    "codeberg.org",
    "git.sr.ht",
    "sr.ht",
)

LOW_CRED_OR_JOKE_URL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|[./])(?:youtube\.com|youtu\.be)(?:/|$)", re.I),
    re.compile(r"google\.com/search", re.I),
    re.compile(r"(?:lmgtfy\.com|letmegooglethat\.com)", re.I),
    re.compile(
        r"reddit\.com/r/(?:ShittySysadmin|BayAreaTalk|wallstreetbets|memes|funny|ProgrammerHumor)",
        re.I,
    ),
    re.compile(r"(?:wiktionary\.org|urbandictionary\.com)", re.I),
    re.compile(r"(?:giphy\.com|tenor\.com|imgflip\.com|knowyourmeme\.com|9gag\.com|tiktok\.com)", re.I),
    re.compile(r"jobs\.nvidia\.com", re.I),
    re.compile(r"nvidia\.com/gtc", re.I),
    re.compile(r"claude\.ai/artifact", re.I),
    re.compile(r"weekand\.com/home-garden", re.I),
    re.compile(r"quoteinvestigator\.com", re.I),
    re.compile(r"leather-jacket-worn-by-nvidia-ceo", re.I),
)

_FORGE_ARTIFACT_PATH_RE = re.compile(
    r"^/[^/]+/[^/]+/(?:-\/)?(?:commit|commits|blob|tree|pull|pulls|merge_requests|issues|releases|compare|discussions|security)(?:/|$)",
    re.I,
)
_FORGE_REPO_PATH_RE = re.compile(r"^/([^/]+)/[^/]+/?$", re.I)
_FORGE_SITE_ROUTES: frozenset[str] = frozenset(
    {
        "about",
        "collections",
        "customer-stories",
        "customer-terms",
        "enterprise",
        "events",
        "explore",
        "features",
        "login",
        "marketplace",
        "orgs",
        "pricing",
        "readme",
        "security",
        "settings",
        "signup",
        "site",
        "sponsors",
        "topics",
        "trending",
    }
)
_DOI_PATH_RE = re.compile(r"/10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
_W3_TR_RE = re.compile(r"^/TR(?:/|$)", re.I)
_GO_DOC_RE = re.compile(r"^/(?:doc|blog|issue|cl)(?:/|$)", re.I)


def _matches_domain(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def _is_gov_or_sovereign(host: str) -> bool:
    return (
        host.endswith(".gov")
        or host.endswith(".mil")
        or host.endswith(".gov.uk")
        or host.endswith(".gov.au")
        or host.endswith(".gc.ca")
        or host.endswith(".europa.eu")
    )


def _is_academic_institution(host: str) -> bool:
    return host.endswith(".edu") or host.endswith(".ac.uk") or host.endswith(".edu.au")


def classify_single_url(url: str) -> SourceMatch:
    """Classify a single external URL into epistemic tier and source family.

    Args:
        url: Raw external href string.

    Returns:
        SourceMatch with tier in {-1, 1, 2, 3} and canonical category label.
    """
    cleaned = url.strip()
    parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned.lstrip('/')}")
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path or ""

    if any(p.search(cleaned) for p in LOW_CRED_OR_JOKE_URL_PATTERNS):
        return SourceMatch(cleaned, host, -1, "low_cred_or_joke", False, True)

    if _matches_domain(host, SEC_DOMAINS):
        return SourceMatch(cleaned, host, 3, "sec_filing", True, False)

    if _matches_domain(host, RFC_STANDARD_DOMAINS) or (
        _matches_domain(host, ("w3.org",)) and _W3_TR_RE.search(path)
    ):
        return SourceMatch(cleaned, host, 3, "rfc_standard", True, False)

    if _matches_domain(host, ARXIV_PREPRINT_DOMAINS):
        return SourceMatch(cleaned, host, 3, "arxiv_preprint", True, False)

    if _matches_domain(host, DOI_PEER_REVIEWED_DOMAINS) or _DOI_PATH_RE.search(path):
        return SourceMatch(cleaned, host, 3, "doi_peer_reviewed", True, False)

    if _matches_domain(host, LWN_DOMAINS):
        return SourceMatch(cleaned, host, 3, "lwn_systems", True, False)

    if _matches_domain(host, KERNEL_AND_TRACKER_DOMAINS) or (
        _matches_domain(host, CODE_FORGE_HOSTS) and _FORGE_ARTIFACT_PATH_RE.search(path)
    ):
        return SourceMatch(cleaned, host, 3, "github_artifact", True, False)

    if _is_gov_or_sovereign(host) or _matches_domain(host, GOV_AND_LEGAL_DOMAINS):
        return SourceMatch(cleaned, host, 3, "gov_legal", True, False)

    if (
        path.lower().endswith(".pdf")
        or _matches_domain(host, TIER3_TECHNICAL_AND_ARCHIVE_DOMAINS)
        or (_matches_domain(host, ("go.dev",)) and _GO_DOC_RE.search(path))
    ):
        return SourceMatch(cleaned, host, 3, "primary_technical_doc", True, False)

    repo_m = _FORGE_REPO_PATH_RE.search(path) if _matches_domain(host, CODE_FORGE_HOSTS) else None
    if repo_m and repo_m.group(1).lower() not in _FORGE_SITE_ROUTES:
        return SourceMatch(cleaned, host, 2, "code_repository", True, False)

    if _matches_domain(host, TIER2_INVESTIGATIVE_DOMAINS) or _is_academic_institution(host):
        return SourceMatch(cleaned, host, 2, "investigative_or_tech_press", True, False)

    return SourceMatch(cleaned, host, 1, "general_web", False, False)


def is_external_citation_url(url: str) -> bool:
    """Return True if href is an external citation rather than an internal HN nav/guideline link."""
    if not url or url.startswith("item?id=") or url.startswith("reply?id=") or url.startswith("user?id="):
        return False
    return "news.ycombinator.com/newsguidelines" not in url


def classify_urls_detailed(urls: list[str]) -> dict[str, Any]:
    """Classify a comment's href list into aggregate epistemic tier, counts, domains, and categories."""
    ext_urls = [u for u in urls if is_external_citation_url(u)]
    if not ext_urls:
        return {
            "url_tier": 0,
            "primary_url_count": 0,
            "low_cred_url_count": 0,
            "url_domains": [],
            "url_categories": [],
        }

    best_tier = 0
    primary_cnt = 0
    low_cnt = 0
    domains: list[str] = []
    categories: list[str] = []

    for u in ext_urls:
        match = classify_single_url(u)
        if match.host:
            domains.append(match.host)
        if match.category not in categories:
            categories.append(match.category)
        if match.is_low_cred:
            low_cnt += 1
            if best_tier == 0:
                best_tier = -1
            continue
        if match.is_primary:
            primary_cnt += 1
        best_tier = max(best_tier, match.tier)

    return {
        "url_tier": best_tier,
        "primary_url_count": primary_cnt,
        "low_cred_url_count": low_cnt,
        "url_domains": domains,
        "url_categories": categories,
    }


def classify_urls(urls: list[str]) -> tuple[int, int, int, list[str]]:
    """Backward-compatible tuple wrapper returning (best_tier, primary_count, low_count, domains)."""
    res = classify_urls_detailed(urls)
    return (
        int(res["url_tier"]),
        int(res["primary_url_count"]),
        int(res["low_cred_url_count"]),
        list(res["url_domains"]),
    )

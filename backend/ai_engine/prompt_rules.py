"""Non-negotiable output rules, spam linting, and deliverability heuristics.

Two things live here:

1. `HARD_RULES` -- constraints appended to *every* generation regardless of what
   the tenant wrote in their own prompt. They are not editable, because a user
   who deletes "no em dashes" doesn't get a stylistic variation, they get mail in
   the spam folder. The settings UI shows them read-only so the behaviour isn't
   mysterious.

2. `lint_email()` -- scores the model's actual output. Prompting reduces bad
   output; it does not guarantee it. Anything that reaches the send path is
   checked again here, because the model is not the last line of defence.
"""
import re

# --------------------------------------------------------------------------
# Rules the model always receives
# --------------------------------------------------------------------------

# Typography and formatting. Em/en dashes are the single strongest "written by
# an LLM" tell in cold email, and ALL-CAPS/!!! are classic filter triggers.
FORMATTING_RULES = """FORMATTING (absolute, no exceptions):
- Never use em dashes or en dashes. Use a comma, a period, or a simple hyphen.
- Never use emojis, emoticons, or decorative unicode.
- Never use ALL CAPS for emphasis. Never use more than one exclamation mark in the whole email.
- Plain text only. No markdown, no bold, no bullet symbols, no headers, no HTML.
- No tracking links, no shortened URLs, no attachments, and at most one link.
- Do not include a signature block, a physical address, or an unsubscribe line. Those are added automatically."""

# Patterns that read as machine-generated. This is the "human pattern" the user
# asked for: real people write unevenly, use contractions, and are specific.
HUMAN_VOICE_RULES = """SOUND LIKE A PERSON, NOT A TEMPLATE:
- Vary sentence length. Mix a short 4-6 word sentence with a longer one. Uniform sentence length reads as generated.
- Use contractions (you're, I'm, we've, don't). Formal uncontracted prose reads as corporate spam.
- Be concrete. Name the actual company, role, or signal. Generic praise is worse than no praise.
- Never open with a pleasantry: no "Hope this email finds you well", "Hope you're doing well", "I hope all is well", "Trust you're having a great week".
- Never use these AI tell-words: delve, leverage, landscape, realm, tapestry, testament, navigate the, in today's fast-paced, seamless, robust, game-changer, unlock, elevate, supercharge, revolutionize, cutting-edge, synergy, holistic, paradigm.
- Do not flatter. No "I was impressed by", "I came across your incredible", "your amazing work".
- Do not describe your own email ("I'll keep this brief", "quick question", "reaching out because").
- Write at roughly an 8th grade reading level. Short words beat long ones."""

# Structural rules. One ask, low commitment, short.
STRUCTURE_RULES = """STRUCTURE:
- 50 to 90 words in the body. Under 50 reads as thin, over 90 does not get read.
- Open with the prospect's specific problem, not with yourself or your company.
- Exactly one call to action, and make it low commitment: a question they can answer in one line. Never ask for a meeting, a demo, or a calendar link in a first touch.
- End with a question mark. A question gets replies; a statement does not.
- Do not mention pricing, discounts, free trials, guarantees, or urgency of any kind."""

# Gmail files mail under Promotions when it reads like marketing, even when it
# passes every spam filter. This is the tab problem, not the spam problem.
PRIMARY_TAB_RULES = """READ AS PERSONAL MAIL, NOT MARKETING (this decides Primary vs Promotions):
- Write as one person emailing another person. Never as a company emailing a prospect.
- Do not include any link in a first touch. Not a calendar link, not a website, not a case study.
- Never use marketing vocabulary: solution, platform, industry-leading, best-in-class, streamline, optimize, empower, transform your, boost your, drive results, ROI, book a demo, schedule a call, learn more, check out our, sign up, get started, webinar, case study, white paper.
- Do not say "we" when you mean your company's product. Say "I".
- No signature block, no company boilerplate, no social links, no logos, no formatted lists.
- Greet them by first name. Never "Hi there", never "Hello," with no name, never leave a merge token like {{first_name}} unfilled.
- If you mention what you do, describe it as a thing you did for someone, not as a product you sell."""

SUBJECT_RULES = """SUBJECT LINE:
- 3 to 7 words. Under 50 characters total.
- Lowercase or sentence case. Never Title Case, never ALL CAPS.
- No punctuation at the end. No exclamation marks. No emojis. No brackets.
- Never fake a reply or forward. Do not start with "Re:", "Fwd:", "Following up on" for a first touch. That is deceptive and is both a spam signal and unlawful under CAN-SPAM.
- No spam trigger words: free, guarantee, act now, limited time, urgent, offer, deal, discount, cash, income, risk-free, winner, congratulations, click here, buy, order, cheap, save big, exclusive.
- It must relate to the body. A subject that does not match the body is a filter trigger.
- Write it like an internal note from a colleague, not like marketing."""

# Assembled once so the prompt bytes are stable (prompt caching friendly).
HARD_RULES = "\n\n".join([
    FORMATTING_RULES, HUMAN_VOICE_RULES, STRUCTURE_RULES, PRIMARY_TAB_RULES, SUBJECT_RULES,
])

OUTPUT_CONTRACT = """Return ONLY a JSON object, no prose before or after, with exactly these keys:
{
  "pain_point": "<one sentence: the specific, concrete problem this person likely has right now, inferred from their role, industry and signals. Not a generic industry trend.>",
  "subject": "<the subject line>",
  "body": "<the email body>"
}"""


def build_system_prompt(user_instructions, tone):
    """Tenant instructions first, immutable rules last.

    Order matters twice over: later instructions carry more weight with most
    models, and keeping the tenant's editable text at the front means their
    edits don't invalidate the cached prefix of the rules block.
    """
    parts = [user_instructions.strip()] if user_instructions and user_instructions.strip() else []
    parts.append(f"TONE: {tone}." if tone else "")
    parts.append(HARD_RULES)
    parts.append(OUTPUT_CONTRACT)
    return "\n\n".join(p for p in parts if p)


# --------------------------------------------------------------------------
# Spam linting (applied to real output, not just requested via prompt)
# --------------------------------------------------------------------------

# Weighted by how much each actually hurts inbox placement.
SPAM_TERMS_HIGH = [
    'act now', 'buy now', 'click here', 'order now', 'risk free', 'risk-free',
    '100% free', 'money back', 'no credit card', 'limited time', 'urgent',
    'winner', 'congratulations you', 'cash bonus', 'earn extra', 'make money',
    'work from home', 'double your', 'guaranteed', 'satisfaction guaranteed',
]

SPAM_TERMS_MEDIUM = [
    'free', 'discount', 'offer', 'deal', 'cheap', 'save big', 'exclusive',
    'promotion', 'sale', 'bonus', 'credit', 'income', 'investment', 'pricing',
    'trial', 'subscribe', 'unsubscribe here', 'best price',
]

AI_TELLS = [
    'delve', 'leverage', 'landscape', 'realm', 'tapestry', 'testament',
    "in today's fast-paced", 'seamless', 'robust', 'game-changer', 'game changer',
    'unlock', 'elevate', 'supercharge', 'revolutionize', 'revolutionise',
    'cutting-edge', 'synergy', 'holistic', 'paradigm', 'furthermore', 'moreover',
]

FILLER_OPENERS = [
    'hope this email finds you well', 'hope this finds you well',
    "hope you're doing well", 'hope you are doing well', 'hope all is well',
    'i hope this message finds you', 'trust you are well', 'i wanted to reach out',
    'i am reaching out', "i'm reaching out", 'quick question',
]

DECEPTIVE_SUBJECT_PREFIXES = ('re:', 'fwd:', 'fw:')

URL_RE = re.compile(r'https?://\S+', re.IGNORECASE)


def _find(haystack, needles):
    lowered = haystack.lower()
    return [n for n in needles if n in lowered]


def lint_email(subject, body):
    """Score generated output for spam and robotic tells.

    Returns {'score': 0-100, 'grade': str, 'issues': [...]}. `score` is a
    deliverability estimate where 100 is clean; every issue carries a `severity`
    so the UI can rank them and the caller can decide what blocks a send.
    """
    subject = (subject or '').strip()
    body = (body or '').strip()
    issues = []

    def flag(severity, field, message, penalty):
        issues.append({'severity': severity, 'field': field, 'message': message, 'penalty': penalty})

    # --- Typography -------------------------------------------------------
    for field, text in (('subject', subject), ('body', body)):
        if '—' in text or '–' in text:
            flag('high', field, 'Contains an em dash or en dash, a strong AI tell.', 15)
        if re.search(r'[\U0001F300-\U0001FAFF☀-➿]', text):
            flag('high', field, 'Contains emoji, which filters penalise in cold outreach.', 12)

    # --- Subject ----------------------------------------------------------
    if not subject:
        flag('high', 'subject', 'Subject line is empty.', 30)
    else:
        if len(subject) > 50:
            flag('medium', 'subject', f'Subject is {len(subject)} characters. Keep it under 50.', 8)
        if subject.lower().startswith(DECEPTIVE_SUBJECT_PREFIXES):
            flag('high', 'subject',
                 'Subject fakes a reply or forward. Deceptive headers violate CAN-SPAM and are a filter trigger.', 25)
        if subject.isupper():
            flag('high', 'subject', 'Subject is ALL CAPS.', 20)
        if subject.count('!') > 0:
            flag('medium', 'subject', 'Exclamation marks in the subject are a classic spam signal.', 10)
        words = subject.split()
        if len(words) > 2 and all(w[:1].isupper() for w in words if w[:1].isalpha()):
            flag('low', 'subject', 'Subject is Title Case. Sentence case reads more like a human.', 4)

    # --- Body -------------------------------------------------------------
    if not body:
        flag('high', 'body', 'Body is empty.', 40)
        return _score(issues)

    word_count = len(body.split())
    if word_count > 150:
        flag('medium', 'body', f'Body is {word_count} words. Cold emails over 150 words rarely get read.', 8)
    elif word_count < 30:
        flag('low', 'body', f'Body is only {word_count} words, which can read as low effort.', 4)

    links = URL_RE.findall(body)
    if len(links) > 1:
        flag('high', 'body', f'{len(links)} links. More than one link sharply increases spam scoring.', 15)

    if body.count('!') > 1:
        flag('medium', 'body', 'More than one exclamation mark.', 8)

    caps_words = [w for w in body.split() if len(w) > 3 and w.isupper()]
    if caps_words:
        flag('medium', 'body', f'ALL CAPS words: {", ".join(caps_words[:3])}.', 8)

    # --- Lexicon ----------------------------------------------------------
    combined = f'{subject}\n{body}'
    for term in _find(combined, SPAM_TERMS_HIGH):
        flag('high', 'content', f'High-risk spam phrase: "{term}".', 12)
    for term in _find(combined, SPAM_TERMS_MEDIUM):
        flag('medium', 'content', f'Spam-associated word: "{term}".', 5)
    for term in _find(body, AI_TELLS):
        flag('low', 'content', f'AI tell-word: "{term}". Rewrite in plainer language.', 4)
    for phrase in _find(body, FILLER_OPENERS):
        flag('medium', 'content', f'Filler opener: "{phrase}". Open with the prospect\'s problem instead.', 6)

    # --- Human-pattern checks --------------------------------------------
    sentences = [s.strip() for s in re.split(r'[.!?]+', body) if s.strip()]
    if len(sentences) >= 3:
        lengths = [len(s.split()) for s in sentences]
        spread = max(lengths) - min(lengths)
        if spread <= 3:
            flag('low', 'body',
                 'Every sentence is nearly the same length, which reads as machine-generated.', 5)

    if "'" not in body and '’' not in body and word_count > 40:
        flag('low', 'body', 'No contractions. Uncontracted prose reads formal and templated.', 4)

    if not body.rstrip().endswith('?'):
        flag('low', 'body', 'Does not end on a question. Questions get materially more replies.', 4)

    return _score(issues)


def _score(issues):
    score = max(0, 100 - sum(i['penalty'] for i in issues))
    if score >= 90:
        grade = 'excellent'
    elif score >= 75:
        grade = 'good'
    elif score >= 55:
        grade = 'needs work'
    else:
        grade = 'high spam risk'

    order = {'high': 0, 'medium': 1, 'low': 2}
    issues.sort(key=lambda i: order[i['severity']])
    return {'score': score, 'grade': grade, 'issues': issues}


# --------------------------------------------------------------------------
# Promotions-tab analysis (distinct from spam)
# --------------------------------------------------------------------------
# Landing in Gmail's Promotions tab is not a spam problem. The message passed
# every filter; Gmail simply categorised it as marketing rather than personal
# correspondence. The signals are different, and several things that *help*
# with spam (notably List-Unsubscribe) actively hurt here.

# Vocabulary that is perfectly legitimate but reads as marketing copy. None of
# these are spam words; they are category signals.
PROMOTIONAL_VOCABULARY = [
    'solution', 'platform', 'leading provider', 'industry-leading', 'best-in-class',
    'streamline', 'optimize', 'optimise', 'empower', 'transform your', 'boost your',
    'drive results', 'roi', 'book a demo', 'schedule a demo', 'schedule a call',
    'book a call', 'learn more', 'check out our', 'our product', 'our platform',
    'our solution', 'we offer', 'our services', 'sign up', 'get started today',
    'special', 'webinar', 'newsletter', 'case study', 'white paper', 'ebook',
]

# Phrases that read as mail-merge scaffolding rather than a written sentence.
MERGE_TELLS = ['{{', '}}', '[first_name]', '[company]', '{first_name}', '{company}', 'hi there,']


def analyze_promotions_risk(subject, body, *, has_unsubscribe_header=False,
                            is_multipart=False, is_html=False, has_tracking_pixel=False):
    """Estimate Gmail Promotions-tab risk for a message.

    Separate from `lint_email` on purpose: a message can be perfectly clean on
    spam and still be filed under Promotions. Returns the same
    {'score', 'grade', 'issues'} shape, where 100 means "reads as a personal
    one-to-one email".
    """
    subject = (subject or '').strip()
    body = (body or '').strip()
    issues = []

    def flag(severity, field, message, penalty):
        issues.append({'severity': severity, 'field': field, 'message': message, 'penalty': penalty})

    # --- Structural signals (the heaviest ones) --------------------------
    if is_html:
        flag('high', 'structure',
             'HTML body. Personal mail is plain text; HTML is one of the strongest Promotions signals.', 25)

    if is_multipart and not is_html:
        flag('medium', 'structure',
             'Multipart MIME wrapper around a single text part. Real person-to-person mail is a bare '
             'text/plain message.', 12)

    if has_tracking_pixel:
        flag('high', 'structure',
             'Tracking pixel detected. Open tracking is a marketing-automation marker.', 20)

    if has_unsubscribe_header:
        flag('high', 'headers',
             'List-Unsubscribe header present. It is required above ~5,000 messages/day, but below that '
             'volume it mainly tells Gmail this is bulk mail. Switch to a plain-text opt-out line.', 20)

    # --- Content signals --------------------------------------------------
    links = URL_RE.findall(body)
    if len(links) == 1:
        flag('medium', 'body', 'Contains a link. First-touch mail with no link stays in Primary far more often.', 10)
    elif len(links) > 1:
        flag('high', 'body', f'{len(links)} links. Multiple links reads as a campaign, not a personal note.', 20)

    combined = f'{subject}\n{body}'
    for term in _find(combined, PROMOTIONAL_VOCABULARY):
        flag('medium', 'content',
             f'Marketing vocabulary: "{term}". Not spam, but it reads as a campaign.', 6)

    for tell in _find(combined, MERGE_TELLS):
        flag('high', 'content',
             f'Mail-merge artifact: "{tell}". Unfilled tokens and generic greetings mark bulk mail.', 15)

    # A long signature block with company details is a newsletter pattern.
    if body.count('\n') > 12:
        flag('low', 'body', 'Many line breaks. Long signatures and formatted blocks read as marketing.', 4)

    if re.search(r'^\s*(unsubscribe|opt out|manage preferences)', body, re.IGNORECASE | re.MULTILINE):
        flag('medium', 'body',
             'Footer-style unsubscribe wording. Phrase it as a sentence, e.g. "reply \'no thanks\' and '
             'I\'ll leave you alone".', 10)

    word_count = len(body.split())
    if word_count > 120:
        flag('low', 'body', f'{word_count} words. Long mail reads as a newsletter.', 5)

    return _score(issues)


def strip_forbidden_characters(text):
    """Last-resort cleanup for things we can fix without changing meaning."""
    if not text:
        return text
    return (
        text.replace('—', ' - ')
            .replace('–', '-')
            .replace('“', '"').replace('”', '"')
            .replace('‘', "'").replace('’', "'")
            .strip()
    )

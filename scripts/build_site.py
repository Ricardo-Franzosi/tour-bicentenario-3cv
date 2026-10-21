#!/usr/bin/env python3
"""Genera el sitio «Tour del Bicentenario 3CV» desde el export de Google Takeout (Blogger).

Uso:
    python scripts/build_site.py "<ruta a Takeout/Blogger>"

Lee Blogs/Tour del Bicentenario 3CV/feed.atom, los videos del blog y las fotos de
Albums/Tour del Bicentenario 3CV. No reescribe los relatos: solo limpia el HTML heredado,
reemplaza imágenes y videos por copias locales y arma la navegación.
"""
import hashlib
import html
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
BLOG = "Tour del Bicentenario 3CV"
SITE = "Tour del Bicentenario 3CV"
BLOG_URL = "https://la-40-en-3cv-por-cuyo.blogspot.com"
NS = {"a": "http://www.w3.org/2005/Atom", "b": "http://schemas.google.com/blogger/2018"}
MONTHS = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio", 7: "julio",
          8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"}

# Etapas del viaje: (título, descripción, slugs de Blogger en orden cronológico)
STAGES = [
    ("Preparativos", "Los autos, el grupo, la primera prueba en ruta y la conferencia de prensa.",
     ["los-preparativos", "la-vuelta-previa", "conferencia-de-prensa-4-dias"]),
    ("Rumbo al Norte", "La salida desde Buenos Aires, el enlace a Tucumán y la subida a Tafí del Valle.",
     ["la-salida", "1-etapa-enlace-bs-as-tucuman", "san-miguel-de-tucuman-tafi-del-valle"]),
    ("Catamarca y La Rioja", "El Infiernillo, Quilmes, la Ruta 40, Fiambalá, Chilecito y la Cuesta de Miranda.",
     ["etapa-tafi-del-valle-fiambala", "fiambala-chilecito", "etapa-chilecito-baldecito"]),
    ("San Juan", "Ischigualasto, Rodeo, la Cuesta del Viento, Barreal y El Leoncito.",
     ["etapa-baldecitos-rodeo", "etapa-rodeo-barreal"]),
    ("Mendoza y el regreso", "Pampa del Leoncito, Villavicencio, Malargüe, El Sosneado, San Rafael y la vuelta.",
     ["etapa-barreal-mendoza", "etapa-mendoza-malargue", "despedida-en-el-sosneado", "el-final"]),
]

DESCRIPTIONS = {
    "los-preparativos": "A catorce días de partir: el sueño de recorrer la 40 cuyana, el grupo y los tres 3CV.",
    "la-vuelta-previa": "La primera prueba en ruta de los fierros: 300 km, bocinazos y pulgares en alto.",
    "conferencia-de-prensa-4-dias": "Presentación del viaje en la Casa de la Provincia de Tucumán y primeras entrevistas.",
    "la-salida": "Llega el día: la caravana del All Black, el Principito y Mafalda deja Buenos Aires.",
    "1-etapa-enlace-bs-as-tucuman": "1344 km de enlace hasta San Miguel de Tucumán y la recepción de Pilar.",
    "san-miguel-de-tucuman-tafi-del-valle": "Conferencia de prensa, la Casa de la Independencia y la trepada a Tafí del Valle.",
    "etapa-tafi-del-valle-fiambala": "El Infiernillo, las Ruinas de Quilmes y la entrada en la mítica Ruta 40.",
    "fiambala-chilecito": "Asado en las termas de Fiambalá, paisaje del Dakar y llegada a Chilecito.",
    "etapa-chilecito-baldecito": "Un mecánico providencial, la Cuesta de Miranda y la noche en Baldecitos.",
    "etapa-baldecitos-rodeo": "El Valle de la Luna, viajeros del mundo y un camino de cornisa de noche hasta Rodeo.",
    "etapa-rodeo-barreal": "Asado en Rodeo, la Cuesta del Viento y una noche de astronomía en El Leoncito.",
    "etapa-barreal-mendoza": "Despedidas, Pampa del Leoncito, ripio y la llegada a la IV Brigada Aérea.",
    "etapa-mendoza-malargue": "Villavicencio, un semieje roto, la 40 de ripio y un atardecer inolvidable.",
    "despedida-en-el-sosneado": "La Niña Encantada, una noche de carpas al pie de la cordillera y un chivo de cacería.",
    "el-final": "El Cañón del Atuel, San Rafael y la vuelta a casa después de 5237 km de magia.",
}

HOME_VIDEO = "1f75b24699fc1f4b"  # Etapa Mendoza - Malargüe
HERO_PHOTO = "25032010367.jpg"
LOGOS = re.compile(r"^(logo-|citroen\.png|tucuman\.png)")  # logos de sponsors del blog, fuera de la galería

NAV = [("index.html", "Inicio"), ("pages/bitacora/index.html", "Bitácora"), ("pages/gallery.html", "Galería"),
       ("pages/prensa.html", "Prensa"), ("pages/about.html", "El viaje")]


def text(e, path):
    return e.findtext(path, "", NS) or ""


def display_date(value):
    y, m, d = (int(x) for x in value[:10].split("-"))
    return f"{d} de {MONTHS[m]} de {y}"


def esc(s):
    return html.escape(s, quote=True)


def slug_of(filename):
    return Path(filename).stem


def clean_name(name):
    stem, ext = Path(name).stem, Path(name).suffix.lower()
    stem = re.sub(r"\(\d+\)$", "", stem)
    stem = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return stem + ext


# ---------------------------------------------------------------- fotos y videos
class Media:
    def __init__(self, takeout):
        self.album = takeout / "Albums" / BLOG
        self.blogdir = takeout / "Blogs" / BLOG
        self.photos = {}      # nombre original (sin «(n)») -> nombre limpio
        self.unique = []      # nombres limpios únicos, en orden
        self.used = set()
        seen = {}
        for p in sorted(self.album.iterdir()):
            if p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".gif"):
                continue
            base = re.sub(r"\(\d+\)(\.[^.]+)$", r"\1", p.name)
            digest = hashlib.md5(p.read_bytes()).hexdigest()
            if digest in seen:
                self.photos.setdefault(base, seen[digest])
                continue
            name = clean_name(base)
            while name in self.unique:
                name = name.replace(".", "-b.", 1)
            seen[digest] = name
            self.photos.setdefault(base, name)
            self.unique.append(name)
            self.src = getattr(self, "src", {})
            self.src[name] = p
        self.videos, by_hash = {}, {}
        for p in sorted(self.blogdir.iterdir()):
            if p.suffix.lower() in (".mp4", ".avi"):
                self.videos[p.stem] = by_hash.setdefault(hashlib.md5(p.read_bytes()).hexdigest(), p)
        self.photos_ci = {k.lower(): v for k, v in self.photos.items()}

    def local(self, url):
        """Devuelve el nombre local de una imagen de Blogger, o None."""
        name = unquote(url.split("?")[0].rsplit("/", 1)[-1]).replace("+", " ")
        return self.photos.get(name) or self.photos_ci.get(name.lower())

    def copy(self):
        img = ROOT / "assets" / "images" / "fotos"
        vid = ROOT / "assets" / "videos"
        for d in (img, vid):
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True)
        for name in self.unique:
            if name in self.used:
                shutil.copy2(self.src[name], img / name)
        for p in set(self.videos.values()):
            shutil.copy2(p, vid / p.name)


# ---------------------------------------------------------------- limpieza del HTML de Blogger
IMAGE_HREF = re.compile(r'href="[^"]*(googleusercontent|bp\.blogspot|\.(jpe?g|png|gif)")', re.I)


def unwrap_image_links(s):
    """Quita los <a> de Blogger que apuntan a la imagen ampliada (la foto local ya enlaza a sí misma)."""
    out, stack = [], []
    for tok in re.split(r"(<a\b[^>]*>|</a>)", s, flags=re.I):
        if re.match(r"<a\b", tok, re.I):
            drop = bool(IMAGE_HREF.search(tok))
            stack.append(drop)
            if drop:
                continue
        elif tok.lower() == "</a>":
            if stack and stack.pop():
                continue
        out.append(tok)
    return "".join(out)


def clean_content(raw, media, prefix, slugs, used_in=None):
    s = raw

    def video(m):
        vid = m.group(1)
        p = media.videos.get(vid)
        if not p:
            return ""
        if p.suffix.lower() == ".avi":
            return (f'<p><a class="download-link" href="{prefix}assets/videos/{p.name}" download>'
                    f'Descargar el video original (AVI) ↓</a></p>')
        return (f'<video controls preload="metadata" playsinline>'
                f'<source src="{prefix}assets/videos/{p.name}" type="video/mp4">'
                f'Tu navegador no reproduce video.</video>')

    s = re.sub(r'<object[^>]*BLOG_video-([0-9a-f]+)[^>]*>.*?</object>', video, s, flags=re.S | re.I)
    s = re.sub(r'<iframe[^>]*video-([0-9a-f]+)[^>]*>.*?</iframe>', video, s, flags=re.S | re.I)

    def photo(m):
        src = m.group("src")
        local = media.local(src)
        if local:
            media.used.add(local)
            if used_in is not None:
                used_in.setdefault(local, [])
            url = f"{prefix}assets/images/fotos/{local}"
        else:
            url = re.sub(r"/s\d+(-h)?/", "/s1600/", src)
        return (f'<figure class="post-photo"><a href="{url}" target="_blank" rel="noopener">'
                f'<img src="{url}" alt="" loading="lazy" decoding="async"></a></figure>')

    s = unwrap_image_links(s)
    s = re.sub(r'<img[^>]*?\ssrc="(?P<src>[^"]+)"[^>]*>', photo, s, flags=re.S | re.I)

    # enlaces internos del blog -> páginas locales
    def link(m):
        path = m.group(1)
        stem = slug_of(path)
        if path.startswith("/p/"):
            target = {"algunas-fotos": "gallery.html", "la-imagen-del-dia": "gallery.html",
                      "gacetilla-de-prensa": "prensa.html", "prensa": "prensa.html"}.get(stem)
            if target:
                return f'href="{prefix}pages/{target}"'
        elif stem in slugs:
            return f'href="{prefix}pages/bitacora/{stem}.html"'
        return f'href="{BLOG_URL}{path}"'

    s = re.sub(r'href="https?://la-40-en-3cv-por-cuyo\.blogspot\.com(/[^"#?]*)"', link, s)

    s = re.sub(r'\s(style|onblur|imageanchor|border|id|class|align|face|size|color)="[^"]*"', "", s)
    s = re.sub(r"</?(font|span)[^>]*>", "", s, flags=re.I)
    s = s.replace("\xa0", " ").replace("&nbsp;", " ")
    s = re.sub(r"<div>\s*(<br\s*/?>\s*)*</div>", "", s)
    s = re.sub(r"(<br\s*/?>\s*){3,}", "<br><br>", s)
    s = re.sub(r"<div>\s*</div>", "", s)
    s = re.sub(r'<a href="([^"]+)"', lambda m: m.group(0) if m.group(1).startswith(("#", prefix)) or "assets/" in m.group(1)
               else f'<a href="{m.group(1)}" target="_blank" rel="noopener noreferrer"', s)
    return s.strip()


def clean_comment(raw):
    s = re.sub(r"<br\s*/?>", "\n", raw)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = re.sub(r"\S+@\S+\.\S+", "[correo omitido]", s)
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n", s) if p.strip()]
    return "".join(f"<p>{esc(p)}</p>" for p in paras)


# ---------------------------------------------------------------- plantillas
def page(title, description, prefix, current, body, extra_css=True):
    nav = "".join(
        f'<a href="{prefix}{href}"{" aria-current=\"page\"" if label == current else ""}>{label}</a>'
        for href, label in NAV)
    css = f'<link rel="stylesheet" href="{prefix}css/styles.css">'
    if extra_css:
        css += f'<link rel="stylesheet" href="{prefix}css/bitacora.css">'
    full_title = SITE if title == SITE else f"{title} · {SITE}"
    return f'''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{esc(description)}">
  <meta name="theme-color" content="#55291a">
  <meta property="og:title" content="{esc(full_title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <title>{esc(full_title)}</title>
  {css}
  <link rel="icon" type="image/svg+xml" href="{prefix}assets/favicon.svg">
</head>
<body>
  <a class="skip-link" href="#contenido">Saltar al contenido</a>
  <header class="site-header">
    <div class="shell header-inner">
      <a class="brand" href="{prefix}index.html" aria-label="{SITE}, inicio">
        <span class="brand-mark" aria-hidden="true">3</span>
        <span>{SITE}</span>
      </a>
      <nav class="nav" aria-label="Navegación principal">{nav}</nav>
    </div>
  </header>
{body}
  <footer class="site-footer">
    <div class="shell footer-inner">
      <div>
        <strong>{SITE}</strong>
        <p>La 40 por Cuyo en Citroën 3CV · marzo–abril de 2010.</p>
      </div>
      <div class="footer-links">
        <a href="{prefix}pages/bitacora/index.html">Bitácora</a>
        <a href="{prefix}pages/gallery.html">Galería</a>
        <a href="{BLOG_URL}/" target="_blank" rel="noopener noreferrer">Blog original</a>
      </div>
    </div>
  </footer>
</body>
</html>
'''


def photo_card(prefix, name, title, caption="", wide=False):
    url = f"{prefix}assets/images/fotos/{name}"
    cap = f"<span>{esc(caption)}</span>" if caption else ""
    return (f'<figure class="photo-card{" photo-wide" if wide else ""}"><a href="{url}" target="_blank" rel="noopener">'
            f'<img src="{url}" alt="{esc(caption or title)}" loading="lazy" decoding="async"></a>'
            f'<figcaption><strong>{esc(title)}</strong>{cap}</figcaption></figure>')


# ---------------------------------------------------------------- armado
def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    takeout = Path(sys.argv[1])
    feed = ET.parse(takeout / "Blogs" / BLOG / "feed.atom").getroot()
    entries = feed.findall("a:entry", NS)
    media = Media(takeout)

    live = lambda e: text(e, "b:status") == "LIVE"
    posts = sorted((e for e in entries if text(e, "b:type") == "POST" and live(e)), key=lambda e: text(e, "a:published"))
    pages_ = {slug_of(text(e, "b:filename")): e for e in entries if text(e, "b:type") == "PAGE" and live(e)}
    comments = {}
    for e in entries:
        if text(e, "b:type") == "COMMENT" and live(e):
            comments.setdefault(text(e, "b:parent"), []).append(e)

    by_slug = {slug_of(text(e, "b:filename")): e for e in posts}
    order = [s for _, _, slugs in STAGES for s in slugs]
    missing = set(by_slug) ^ set(order)
    if missing:
        sys.exit(f"Entradas sin etapa asignada o inexistentes: {sorted(missing)}")
    slugs = set(order)

    out = ROOT / "pages" / "bitacora"
    out.mkdir(parents=True, exist_ok=True)
    photo_chapter = {}   # foto -> slug del primer capítulo que la usa
    n_comments = 0

    # --- capítulos
    for i, slug in enumerate(order):
        e = by_slug[slug]
        title = text(e, "a:title").strip()
        date = display_date(text(e, "a:published"))
        stage = next(t for t, _, ss in STAGES if slug in ss)
        used = {}
        body = clean_content(text(e, "a:content"), media, "../../", slugs, used)
        for name in used:
            photo_chapter.setdefault(name, slug)
        cs = sorted(comments.get(text(e, "a:id"), []), key=lambda c: text(c, "a:published"))
        n_comments += len(cs)
        com_html = ""
        if cs:
            items = "".join(
                f'<article class="comment"><header><strong>{esc(text(c, "a:author/a:name") or "Anónimo")}</strong>'
                f'<time datetime="{text(c, "a:published")[:10]}">{display_date(text(c, "a:published"))}</time></header>'
                f'<div class="comment-body">{clean_comment(text(c, "a:content"))}</div></article>' for c in cs)
            com_html = (f'<section class="journal-comments card" aria-labelledby="comentarios"><p class="eyebrow">'
                        f'{len(cs)} comentario{"s" if len(cs) != 1 else ""}</p><h2 id="comentarios">Comentarios del blog original</h2>{items}</section>')
        prev_ = (f'<a href="./{order[i-1]}.html"><span>← Anterior</span><strong>{esc(text(by_slug[order[i-1]], "a:title").strip())}</strong></a>'
                 if i else '<a href="./index.html"><span>← Índice</span><strong>La bitácora completa</strong></a>')
        next_ = (f'<a href="./{order[i+1]}.html"><span>Siguiente →</span><strong>{esc(text(by_slug[order[i+1]], "a:title").strip())}</strong></a>'
                 if i + 1 < len(order) else '<a href="./index.html"><span>Volver →</span><strong>La bitácora completa</strong></a>')
        main_html = f'''  <main class="shell" id="contenido">
    <section class="page-hero chapter-hero"><p class="eyebrow">{esc(stage)} · Capítulo {i+1:02d} de {len(order)} · {date}</p><h1>{esc(title)}</h1>
    <p class="lead">{esc(DESCRIPTIONS[slug])}</p></section>
    <article class="journal-entry card"><div class="journal-entry-body">{body}</div><footer class="journal-source"><span>Texto original de la bitácora · {date}</span><a href="{BLOG_URL}{text(e, "b:filename")}" target="_blank" rel="noopener noreferrer">Ver publicación original en Blogger ↗</a></footer></article>
    {com_html}
    <nav class="chapter-nav" aria-label="Navegación entre capítulos">{prev_}{next_}</nav>
  </main>'''
        (out / f"{slug}.html").write_text(page(title, f"{title} · {DESCRIPTIONS[slug]}", "../../", "Bitácora", main_html), encoding="utf-8")

    # --- índice de la bitácora
    first, last = by_slug[order[0]], by_slug[order[-1]]
    stages_html = ""
    for n, (stitle, sdesc, ss) in enumerate(STAGES, 1):
        cards = "".join(
            f'<article class="timeline-card"><p class="timeline-date">{display_date(text(by_slug[s], "a:published"))}</p>'
            f'<h3>{esc(text(by_slug[s], "a:title").strip())}</h3><p>{esc(DESCRIPTIONS[s])}</p><a href="./{s}.html">Leer capítulo →</a></article>'
            for s in ss)
        stages_html += (f'<section class="timeline-stage" id="etapa-{n}"><header><p class="eyebrow">Etapa {n:02d}</p><h2>{esc(stitle)}</h2></header>'
                        f'<div class="timeline-grid">{cards}</div></section>')
    idx = f'''  <main class="shell" id="contenido">
    <section class="page-hero logbook-hero"><p class="eyebrow">Archivo de viaje · 2010</p><h1>La bitácora completa</h1>
    <p class="lead">{len(order)} relatos escritos sobre la marcha, muchas veces con poca señal y mucho polvo, ordenados cronológicamente y reunidos aquí con la voz con la que fueron escritos.</p>
    <div class="logbook-meta"><span>{len(order)} entradas originales</span><span>{display_date(text(first, "a:published"))} – {display_date(text(last, "a:published"))}</span><span>Buenos Aires → Ruta 40 cuyana → Buenos Aires</span></div></section>
    <section class="logbook-note"><p class="eyebrow">Criterio editorial</p><h2>El texto sigue siendo el del viaje</h2>
    <p>La web organiza y presenta los relatos; no los reescribe. Las fotos y los videos se sirven desde copias locales del archivo del blog, y cada capítulo conserva sus comentarios y un enlace a la publicación original de Blogger.</p></section>
    {stages_html}
  </main>'''
    (out / "index.html").write_text(page("Bitácora", "Bitácora cronológica completa del Tour del Bicentenario en Citroën 3CV por la Ruta 40 cuyana.", "../../", "Bitácora", idx), encoding="utf-8")

    # --- galería
    gal_sections = []
    used_pages = {}
    for key, gtitle, gdesc in (("la-imagen-del-dia", "La imagen del día", "Las fotos elegidas día a día durante el viaje."),
                               ("algunas-fotos", "Algunas fotos", "La selección publicada en el blog, con sus epígrafes originales.")):
        e = pages_.get(key)
        if e is None:
            continue
        raw = text(e, "a:content")
        cards = []
        # epígrafe original: texto que sigue a cada imagen hasta la próxima
        parts = re.split(r'(<img[^>]*?\ssrc="[^"]+"[^>]*>)', raw)
        for j, part in enumerate(parts):
            m = re.match(r'<img[^>]*?\ssrc="([^"]+)"', part)
            if not m:
                continue
            local = media.local(m.group(1))
            if not local or local in used_pages:
                continue
            nxt = parts[j + 1] if j + 1 < len(parts) else ""
            cap = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", nxt))).strip(" .-") if key == "algunas-fotos" else ""
            used_pages[local] = key
            media.used.add(local)
            cards.append(photo_card("../", local, gtitle, cap[:220]))
        if cards:
            gal_sections.append((gtitle, gdesc, cards))
    chapter_cards = {}
    for name, slug in photo_chapter.items():
        if name in used_pages:
            continue
        chapter_cards.setdefault(slug, []).append(name)
    for slug in order:
        if slug in chapter_cards:
            t = text(by_slug[slug], "a:title").strip()
            gal_sections.append((t, DESCRIPTIONS[slug], [photo_card("../", n, t, display_date(text(by_slug[slug], "a:published"))) for n in chapter_cards[slug]]))
    rest = [n for n in media.unique if n not in used_pages and n not in photo_chapter and not LOGOS.match(n)]
    if rest:
        gal_sections.append(("Más imágenes del archivo", "Fotos del álbum del blog que no quedaron asociadas a una entrada.",
                             [photo_card("../", n, "Tour del Bicentenario") for n in rest]))
        media.used.update(rest)
    gal_html = "".join(
        f'<section class="timeline-stage"><header><p class="eyebrow">{len(cards)} foto{"s" if len(cards) != 1 else ""}</p><h2>{esc(t)}</h2></header>'
        f'<p class="gallery-intro">{esc(d)}</p><div class="gallery-grid gallery-dense">{"".join(cards)}</div></section>'
        for t, d, cards in gal_sections)
    total_photos = len(media.unique)
    gal = f'''  <main class="shell" id="contenido">
    <section class="page-hero logbook-hero"><p class="eyebrow">Bitácora visual</p><h1>Imágenes del Tour</h1>
    <p class="lead">Las Citronaves, la Ruta 40, los paisajes de Cuyo y la gente que fuimos cruzando, tal como quedaron en el álbum del blog.</p>
    <div class="logbook-meta"><span>{total_photos} fotografías</span><span>Marzo–abril de 2010</span><span>Fotos de Paula, Martín, Pablo y el grupo</span></div></section>
    {gal_html}
  </main>'''
    (ROOT / "pages" / "gallery.html").write_text(page("Galería", "Galería fotográfica del Tour del Bicentenario 3CV por la Ruta 40 cuyana.", "../", "Galería", gal), encoding="utf-8")

    # --- prensa
    press_parts = []
    for key, ptitle in (("gacetilla-de-prensa", "Gacetilla de prensa"), ("prensa", "Repercusiones en los medios")):
        e = pages_.get(key)
        if e is None:
            continue
        body = clean_content(text(e, "a:content"), media, "../", slugs)
        press_parts.append(f'<article class="journal-entry card"><p class="eyebrow">{display_date(text(e, "a:published"))}</p><h2>{ptitle}</h2>'
                           f'<div class="journal-entry-body">{body}</div><footer class="journal-source"><span>Página original del blog</span>'
                           f'<a href="{BLOG_URL}{text(e, "b:filename")}" target="_blank" rel="noopener noreferrer">Ver en Blogger ↗</a></footer></article>')
    prensa = f'''  <main class="shell" id="contenido">
    <section class="page-hero chapter-hero"><p class="eyebrow">Experiencia 3CV · Ruta 40 región de Cuyo</p><h1>Prensa</h1>
    <p class="lead">La gacetilla que repartimos en la conferencia de prensa y las notas, radios y diarios que se hicieron eco del viaje.</p></section>
    {"".join(press_parts)}
    <nav class="chapter-nav" aria-label="Relacionado"><a href="./bitacora/conferencia-de-prensa-4-dias.html"><span>Capítulo 03</span><strong>Conferencia de Prensa</strong></a><a href="./bitacora/index.html"><span>Volver →</span><strong>La bitácora completa</strong></a></nav>
  </main>'''
    (ROOT / "pages" / "prensa.html").write_text(page("Prensa", "Gacetilla y repercusiones en los medios del Tour del Bicentenario 3CV.", "../", "Prensa", prensa), encoding="utf-8")

    # --- home
    stage_cards = ""
    for n, (stitle, sdesc, ss) in enumerate(STAGES, 1):
        stage_cards += (f'<a class="journey-card{" journey-card-featured" if n == len(STAGES) else ""}" href="./pages/bitacora/{ss[0]}.html">'
                        f'<span>{n:02d}</span><strong>{esc(stitle)}</strong><small>{esc(sdesc)}</small></a>')
    hero = media.photos.get(HERO_PHOTO)
    media.used.add(hero)
    vid = media.videos[HOME_VIDEO].name
    home = f'''  <main id="contenido">
    <section class="hero">
      <div class="shell hero-grid">
        <div class="hero-copy">
          <p class="eyebrow">Ruta 40 · Región de Cuyo · 2010</p>
          <h1>La 40 por Cuyo en 3CV</h1>
          <p class="lead">Un grupo de amigos, tres Citroën 3CV y un sueño: recorrer la Ruta 40 cuyana a 80 km por hora, porque la felicidad está en disfrutar el camino.</p>
          <div class="hero-actions">
            <a class="button" href="./pages/bitacora/index.html">Leer la bitácora</a>
            <a class="text-link" href="./pages/gallery.html">Ver la galería <span aria-hidden="true">→</span></a>
            <a class="text-link" href="{BLOG_URL}/" target="_blank" rel="noopener noreferrer">Blog original <span aria-hidden="true">↗</span></a>
          </div>
        </div>
        <figure class="hero-media">
          <img src="./assets/images/fotos/{hero}" alt="Las Citronaves en la ruta" decoding="async" fetchpriority="high">
          <figcaption>Una Citronave en la ruta · marzo de 2010</figcaption>
        </figure>
      </div>
    </section>

    <section class="shell" aria-labelledby="intro-title">
      <article class="card prose page-card">
        <header class="article-heading"><p class="eyebrow">Capítulo 1</p><h2 id="intro-title">Los preparativos</h2></header>
        <p>«Este espacio pretende ser un relato de los acontecimientos de un grupo de personas que tienen un sueño: recorrer la cuarenta en un 3CV por la región de Cuyo.»</p>
        <p>Del 20 de marzo al 3 de abril de 2010, el All Black, el Principito y Mafalda —escoltados por un Citroën C3— unieron Buenos Aires con Tucumán, Catamarca, La Rioja, San Juan y Mendoza: 5237 kilómetros de ripio, cuestas, mecánica de ruta y amigos nuevos.</p>
        <a class="gallery-link" href="./pages/bitacora/los-preparativos.html">Leer el primer capítulo →</a>
      </article>
    </section>

    <section class="journey-overview shell" aria-labelledby="ruta-viaje">
      <div class="journey-heading">
        <div><p class="eyebrow">Un viaje, cinco etapas</p><h2 id="ruta-viaje">De Buenos Aires a la Ruta 40 cuyana</h2></div>
        <p>La bitácora está ordenada en cinco etapas para seguir el viaje desde los preparativos hasta la vuelta a casa.</p>
      </div>
      <div class="journey-cards">{stage_cards}</div>
    </section>

    <section class="shell video-section" aria-labelledby="video-title">
      <div class="section-heading video-heading">
        <div><p class="eyebrow">Etapa Mendoza – Malargüe</p><h2 id="video-title">Las Citronaves en la 40</h2></div>
        <p>Uno de los videos filmados durante el viaje: ripio, lomadas de pastizales y los 3CV «abriendo la tranquera a los potros salvajes».</p>
      </div>
      <div class="video-wrap"><video controls preload="metadata" playsinline><source src="./assets/videos/{vid}" type="video/mp4">Tu navegador no reproduce video.</video></div>
    </section>
  </main>'''
    (ROOT / "index.html").write_text(page(SITE, "Bitácora del Tour del Bicentenario: la Ruta 40 por Cuyo en tres Citroën 3CV, marzo–abril de 2010.", "./", "Inicio", home), encoding="utf-8")

    media.copy()
    print(f"Capítulos: {len(order)} · comentarios: {n_comments} · fotos: {len(media.unique)} "
          f"(en capítulos: {len(photo_chapter)}) · videos: {len(set(media.videos.values()))}")


if __name__ == "__main__":
    main()

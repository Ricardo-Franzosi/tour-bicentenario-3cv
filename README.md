# Tour del Bicentenario 3CV · La 40 por Cuyo

Sitio web estático que reúne la bitácora del **Tour del Bicentenario**: el viaje de un grupo de amigos en tres **Citroën 3CV** —el All Black, el Principito y Mafalda— por la **Ruta 40 en la región de Cuyo**, del 20 de marzo al 3 de abril de 2010.

El sitio nace del blog original [la-40-en-3cv-por-cuyo.blogspot.com](https://la-40-en-3cv-por-cuyo.blogspot.com/) y sigue el modelo de [Atlantis · Fin del Mundo](https://github.com/Ricardo-Franzosi/atlantis-fin-del-mundo).

## Contenido

- **15 entradas originales de Blogger** ordenadas cronológicamente en cinco etapas: Preparativos, Rumbo al Norte, Catamarca y La Rioja, San Juan, y Mendoza y el regreso.
- Fechas en castellano, capítulos numerados y navegación anterior/siguiente.
- Los comentarios del blog original al pie de cada capítulo (solo nombre y fecha; sin datos de contacto).
- Fotos y videos servidos desde copias locales del archivo del blog (Google Takeout), sin depender de Blogger.
- Galería con «La imagen del día», «Algunas fotos» con sus epígrafes originales y las fotos de cada etapa.
- Página de **Prensa** con la gacetilla y las repercusiones en los medios, y página **El viaje** con el grupo, las Citronaves y el recorrido.
- Los relatos no se reescriben: solo se limpia el HTML heredado de Blogger.
- HTML y CSS sin frameworks, diseño responsive y accesibilidad básica.

## Estructura

```text
tour-bicentenario-3cv/
├── .github/workflows/pages.yml
├── assets/
│   ├── images/fotos/
│   └── videos/
├── css/
│   ├── styles.css
│   └── bitacora.css
├── pages/
│   ├── bitacora/
│   ├── gallery.html
│   ├── prensa.html
│   └── about.html
├── scripts/build_site.py
└── index.html
```

## Regenerar el sitio

```bash
python scripts/build_site.py "<ruta a Takeout/Blogger>"
```

El script lee `Blogs/Tour del Bicentenario 3CV/feed.atom`, los videos del blog y el álbum de fotos del export de Google Takeout. `pages/about.html` se mantiene a mano.

## Publicación

Los cambios en `main` se despliegan con GitHub Pages:

`https://ricardo-franzosi.github.io/tour-bicentenario-3cv/`

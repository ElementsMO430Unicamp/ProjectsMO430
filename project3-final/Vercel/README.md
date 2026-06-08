# Long COVID Expression — Pathway 3D

Visualização isométrica 3D do mapa KEGG **map05171** com barras de log2 fold change por área gênica (dados `silver_pathway_areasv1.csv`).

## Estrutura

```text
pathwayApp/
  ├── pathwaylog2foldchange3d.html   # app gerado (fonte do deploy)
  ├── build_pathway_log2foldchange3d.py
  ├── silver_pathway_areasv1.csv
  └── map05171@2x_20260606_220006.png
public/                              # artefato estático servido na Vercel
  ├── index.html
  └── map05171@2x_20260606_220006.png
scripts/
  └── sync-public.mjs                # copia pathwayApp → public no build
```

## Desenvolvimento local

```bash
npm install
npm run dev
```

Abre em [http://localhost:4321](http://localhost:4321).

## Regenerar o HTML após mudar o CSV

```bash
python pathwayApp/build_pathway_log2foldchange3d.py
npm run build
```

## Deploy na Vercel

O projeto é **estático**: `npm run build` copia `pathwayApp/pathwaylog2foldchange3d.html` para `public/index.html` e publica a pasta `public/`.

Conecte o repositório na Vercel — não é necessário framework preset; o `vercel.json` já define build e output.

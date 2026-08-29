# Bundled NLTK data

The English `punkt_tab` data and NLTK stopword corpus are bundled for LlamaIndex so
startup never invokes `nltk.download()` in an intranet deployment. The empty
`tokenizers/punkt` marker works around the LlamaIndex 0.11.x startup check, while NLTK
3.9 uses the bundled `punkt_tab/english` data at runtime.

Source: [nltk_data](https://github.com/nltk/nltk_data). Corpus-specific notices are
kept in `corpora/stopwords/README`.

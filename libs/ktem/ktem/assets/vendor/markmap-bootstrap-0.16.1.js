(function () {
  "use strict";

  if (window.ktemMarkmapReady) return;

  const bootstrapScript = document.currentScript;
  if (!bootstrapScript) {
    console.error("Mindmap bootstrap script cannot determine its asset path.");
    return;
  }

  const assetBase = bootstrapScript.src.replace(/[^/]+(?:\?.*)?$/, "");
  const loadScript = (fileName) =>
    new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = new URL(fileName, assetBase).href;
      script.async = false;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`Unable to load ${fileName}`));
      document.head.appendChild(script);
    });

  const bootstrap = async () => {
    const dependencies = [
      "d3-7.8.5.min.js",
      "markmap-lib-0.16.1.min.js",
      "markmap-view-0.16.0.min.js",
      "markmap-toolbar-0.16.0.min.js",
    ];
    for (const dependency of dependencies) {
      await loadScript(dependency);
    }

    window.markmap = window.markmap || {};
    window.markmap.autoLoader = {
      baseJs: [],
      baseCss: [],
      transformPlugins: [],
      manual: true,
      toolbar: false,
    };
    await loadScript("markmap-autoloader-0.16.1.min.js");
    await window.markmap.autoLoader.ready;

    window.ktemRenderMindmap = (element) => {
      if (!element) return null;
      if (element.__ktemMarkmap) return element.__ktemMarkmap;

      const source = (element.textContent || "")
        .split("\n")
        .map((line) => line.trimEnd())
        .join("\n")
        .trim();
      if (!source) return null;

      const { Transformer, Markmap, Toolbar, deriveOptions } = window.markmap;
      const transformer = new Transformer();
      const { root, frontmatter } = transformer.transform(source);
      const options = deriveOptions(frontmatter?.markmap);

      element.innerHTML = "<svg></svg>";
      const svg = element.firstElementChild;
      const mindmap = Markmap.create(svg, { embedGlobalCSS: false });
      mindmap.setData(root, options);
      mindmap.fit();

      if (Toolbar) {
        const { el } = Toolbar.create(mindmap);
        el.classList.add("ktem-mindmap-toolbar");
        element.append(el);
      }

      element.__ktemMarkmap = mindmap;
      element.__ktemMindmapSource = source;
      return mindmap;
    };
  };

  window.ktemMarkmapReady = bootstrap();
  window.ktemMarkmapReady.catch((error) => {
    console.error("Unable to initialize the offline mindmap renderer.", error);
  });
})();

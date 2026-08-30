function run() {
  const chatTab = document.getElementById("chat-tab");
  const mainParent = chatTab && chatTab.parentNode;
  if (!mainParent) return;

  const headerBar = mainParent.firstElementChild;
  if (headerBar) headerBar.classList.add("header-bar");
  mainParent.style.padding = "0";
  mainParent.style.margin = "0";
  if (mainParent.parentNode) mainParent.parentNode.style.gap = "0";
  if (mainParent.parentNode && mainParent.parentNode.parentNode) {
    mainParent.parentNode.parentNode.style.padding = "0";
  }

  // add favicon
  const favicon = document.createElement("link");
  // set favicon attributes
  favicon.rel = "icon";
  favicon.type = "image/svg+xml";
  favicon.href = "/favicon.ico";
  document.head.appendChild(favicon);

  // setup conversation dropdown placeholder
  const convDropdown = document.querySelector("#conversation-dropdown input");
  if (convDropdown) convDropdown.placeholder = "浏览会话记录";

  const icon = {
    plus:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
    microphone:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15a3.5 3.5 0 0 0 3.5-3.5v-5a3.5 3.5 0 1 0-7 0v5A3.5 3.5 0 0 0 12 15Z"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M9 21h6"/></svg>',
    send:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M6.5 10.5 12 5l5.5 5.5"/></svg>',
    copy:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>',
    edit:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 20 4.2-1 10.3-10.3a2.1 2.1 0 0 0-3-3L5.2 16 4 20Z"/><path d="m13.8 7.4 3 3"/></svg>',
    delete:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/></svg>',
  };

  const setIconButton = (button, markup, label) => {
    if (!button) return;
    if (button.dataset.ktemIcon !== label || !button.querySelector("svg")) {
      button.innerHTML = markup;
      button.dataset.ktemIcon = label;
    }
    if (button.title !== label) button.title = label;
    if (button.getAttribute("aria-label") !== label) {
      button.setAttribute("aria-label", label);
    }
  };

  const resolveButton = (root) =>
    root && (root.matches("button") ? root : root.querySelector("button"));

  const generatedTextTranslations = new Map([
    ["Warning", "警告"],
    ["Error", "错误"],
    ["Info", "提示"],
    ["Success", "成功"],
  ]);
  const localizeTextNode = (textNode) => {
    const rawText = textNode.nodeValue || "";
    const trimmedText = rawText.trim();
    const translatedText = generatedTextTranslations.get(trimmedText);
    if (translatedText) {
      textNode.nodeValue = rawText.replace(trimmedText, translatedText);
    }
  };
  const localizeGeneratedText = (root) => {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) {
      localizeTextNode(root);
      return;
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let textNode = walker.nextNode();
    while (textNode) {
      localizeTextNode(textNode);
      textNode = walker.nextNode();
    }
  };
  new MutationObserver((records) => {
    records.forEach((record) => {
      if (record.type === "characterData") localizeGeneratedText(record.target);
      record.addedNodes.forEach(localizeGeneratedText);
    });
  }).observe(document.body, {
    characterData: true,
    childList: true,
    subtree: true,
  });
  localizeGeneratedText(document.body);

  // Use one action slot: microphone while empty, send while text/files exist,
  // and a recording indicator while ASR is active.
  const composerRow = document.getElementById("chat-composer-row");
  const chatInput = document.getElementById("chat-input");
  if (composerRow && chatInput) {
    const syncComposerAction = () => {
      const textarea = chatInput.querySelector("textarea");
      const sendButton = resolveButton(
        document.getElementById("chat-submit-button")
      );
      const startButton = resolveButton(
        document.getElementById("asr-start-button")
      );
      const stopButton = resolveButton(
        document.getElementById("asr-stop-button")
      );
      const nativeButtons = chatInput.querySelectorAll("button");
      const nativeSubmit = nativeButtons[nativeButtons.length - 1];
      const uploadButton = chatInput.querySelector(
        "button[data-testid='upload-button']"
      );
      if (nativeSubmit && !nativeSubmit.classList.contains("ktem-native-submit")) {
        nativeSubmit.classList.add("ktem-native-submit");
      }
      if (uploadButton) {
        uploadButton.classList.add("ktem-image-upload");
        setIconButton(uploadButton, icon.plus, "添加图片");
      }

      setIconButton(sendButton, icon.send, "发送消息");
      setIconButton(startButton, icon.microphone, "开始实时语音转写");
      if (stopButton) {
        if (!stopButton.querySelector(".asr-running-indicator")) {
          stopButton.innerHTML =
            '<span class="asr-running-indicator" aria-hidden="true"><i></i><i></i><i></i></span>';
        }
        stopButton.title = "取消录音";
        stopButton.setAttribute("aria-label", "取消录音");
      }

      const hasText = Boolean(textarea && textarea.value.trim());
      const hasFiles = Boolean(
        chatInput.querySelector(
          ".thumbnail-item, .file-preview, .file-container, [data-testid='file-preview']"
        )
      );
      composerRow.classList.toggle("has-message-content", hasText || hasFiles);
    };

    const textarea = chatInput.querySelector("textarea");
    if (textarea) textarea.addEventListener("input", syncComposerAction);
    new MutationObserver(syncComposerAction).observe(composerRow, {
      childList: true,
      subtree: true,
    });
    syncComposerAction();
  }

  const dispatchMessageAction = (bridgeId, payload) => {
    const payloadRoot = document.getElementById("chat-message-action-payload");
    const payloadInput = payloadRoot && payloadRoot.querySelector("textarea, input");
    const bridgeRoot = document.getElementById(bridgeId);
    const bridgeButton =
      bridgeRoot &&
      (bridgeRoot.matches("button") ? bridgeRoot : bridgeRoot.querySelector("button"));
    if (!payloadInput || !bridgeButton) return false;

    payloadInput.value = JSON.stringify(payload);
    payloadInput.dispatchEvent(new Event("input", { bubbles: true }));
    payloadInput.dispatchEvent(new Event("change", { bubbles: true }));
    bridgeButton.click();
    return true;
  };

  // Gradio does not render a stable action bar for user messages across versions,
  // so attach a dedicated copy/edit/delete bar to every user-side row.
  const chatbotRoot = document.getElementById("main-chat-bot");
  if (chatbotRoot) {
    let observedUserMessageCount = chatbotRoot.querySelectorAll(
      ".message-row.user-row"
    ).length;
    let activePromptRow = null;
    let promptAnchorSessionActive = false;
    let promptAnchorReleaseTimer = null;
    const scrollPromptToTop = () => {
      if (!activePromptRow || !activePromptRow.isConnected) return;
      let scrollContainer = activePromptRow.parentElement;
      while (scrollContainer && scrollContainer !== chatbotRoot.parentElement) {
        const overflowY = window.getComputedStyle(scrollContainer).overflowY;
        if (
          /(auto|scroll)/.test(overflowY) &&
          scrollContainer.scrollHeight > scrollContainer.clientHeight
        ) {
          const promptRect = activePromptRow.getBoundingClientRect();
          const containerRect = scrollContainer.getBoundingClientRect();
          scrollContainer.scrollTop += promptRect.top - containerRect.top - 8;
          return;
        }
        scrollContainer = scrollContainer.parentElement;
      }
      activePromptRow.scrollIntoView({ behavior: "auto", block: "start" });
    };
    const anchorLatestPrompt = (releaseWhenIdle) => {
      if (!activePromptRow || !activePromptRow.isConnected) return;
      window.requestAnimationFrame(scrollPromptToTop);
      window.setTimeout(scrollPromptToTop, 80);
      window.setTimeout(scrollPromptToTop, 360);
      if (releaseWhenIdle) {
        window.clearTimeout(promptAnchorReleaseTimer);
        promptAnchorReleaseTimer = window.setTimeout(() => {
          activePromptRow = null;
          promptAnchorSessionActive = false;
        }, 3000);
      }
    };
    const releasePromptAnchor = () => {
      activePromptRow = null;
      promptAnchorSessionActive = false;
      window.clearTimeout(promptAnchorReleaseTimer);
    };
    chatbotRoot.addEventListener("wheel", releasePromptAnchor, { passive: true });
    chatbotRoot.addEventListener("touchmove", releasePromptAnchor, { passive: true });
    const userMessageText = (message) => {
      if (!message) return "";
      const clone = message.cloneNode(true);
      clone.querySelectorAll("[data-ktem-chat-attachments]").forEach((node) => {
        node.remove();
      });
      return clone.innerText.trim();
    };
    const userMessageFiles = (message) => {
      if (!message) return [];
      return Array.from(
        message.querySelectorAll("[data-ktem-chat-attachments] img")
      ).flatMap((image) => {
        try {
          const pathname = new URL(image.src, window.location.href).pathname;
          const marker = "/file=";
          const markerIndex = pathname.indexOf(marker);
          if (markerIndex < 0) return [];
          return [decodeURIComponent(pathname.slice(markerIndex + marker.length))];
        } catch (_error) {
          return [];
        }
      });
    };
    const localizeAssistantActions = () => {
      chatbotRoot.querySelectorAll(".message-buttons-left").forEach((actionBar) => {
        actionBar.querySelectorAll("button").forEach((button) => {
          let label = "";
          let title = "";
          if (button.classList.contains("dislike-button")) {
            label = "不满意";
            title = "不满意";
          } else if (button.classList.contains("like-button")) {
            label = "满意";
            title = "满意";
          } else {
            label = "复制回答";
            title = "复制";
          }
          button.setAttribute("aria-label", label);
          button.title = title;
        });
      });
    };

    const enhanceUserMessages = () => {
      localizeAssistantActions();
      const userRows = chatbotRoot.querySelectorAll(".message-row.user-row");
      if (userRows.length > observedUserMessageCount) {
        activePromptRow = userRows[userRows.length - 1];
        promptAnchorSessionActive = true;
        window.clearTimeout(promptAnchorReleaseTimer);
      }
      observedUserMessageCount = userRows.length;
      if (promptAnchorSessionActive && userRows.length) {
        activePromptRow = userRows[userRows.length - 1];
      }
      const messageRows = Array.from(
        chatbotRoot.querySelectorAll(".message-row")
      );
      const activePromptIndex = messageRows.indexOf(activePromptRow);
      const responseStarted =
        activePromptIndex >= 0 &&
        messageRows
          .slice(activePromptIndex + 1)
          .some((row) => row.classList.contains("bot-row"));
      anchorLatestPrompt(responseStarted);

      let historyIndex = -1;
      let previousWasUser = false;
      chatbotRoot.querySelectorAll(".message-row").forEach((row) => {
        const isUser = row.classList.contains("user-row");
        if (isUser || !previousWasUser) historyIndex += 1;
        previousWasUser = isUser;
        if (!isUser) return;

        row.dataset.ktemHistoryIndex = String(historyIndex);
        if (row.querySelector(".ktem-user-message-actions")) return;

        const actionBar = document.createElement("div");
        actionBar.className = "ktem-user-message-actions";

        const copyButton = document.createElement("button");
        copyButton.type = "button";
        copyButton.className = "chat-message-action chat-message-copy";
        copyButton.innerHTML = icon.copy;
        copyButton.title = "复制";
        copyButton.setAttribute("aria-label", "复制消息");

        const editButton = document.createElement("button");
        editButton.type = "button";
        editButton.className = "chat-message-action chat-message-edit";
        editButton.innerHTML = icon.edit;
        editButton.title = "修改";
        editButton.setAttribute("aria-label", "修改消息");

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "chat-message-action chat-message-delete";
        deleteButton.innerHTML = icon.delete;
        deleteButton.title = "删除";
        deleteButton.setAttribute("aria-label", "删除消息");

        copyButton.addEventListener("click", async () => {
          const message = row.querySelector(".message.user");
          const text = userMessageText(message);
          if (!text) return;
          try {
            await navigator.clipboard.writeText(text);
            copyButton.title = "已复制";
            window.setTimeout(() => {
              copyButton.title = "复制";
            }, 1200);
          } catch (_error) {
            window.prompt("请复制消息内容", text);
          }
        });

        editButton.addEventListener("click", () => {
          if (row.querySelector(".chat-message-editor")) return;
          const message = row.querySelector(".message.user");
          if (!message) return;

          const editor = document.createElement("div");
          editor.className = "chat-message-editor";
          const textarea = document.createElement("textarea");
          textarea.value = userMessageText(message);
          textarea.setAttribute("aria-label", "修改问题内容");
          const controls = document.createElement("div");
          controls.className = "chat-message-editor-actions";
          const cancelButton = document.createElement("button");
          cancelButton.type = "button";
          cancelButton.className = "chat-edit-cancel";
          cancelButton.textContent = "取消";
          const sendButton = document.createElement("button");
          sendButton.type = "button";
          sendButton.className = "chat-edit-send";
          sendButton.textContent = "发送";
          controls.append(cancelButton, sendButton);
          editor.append(textarea, controls);
          message.hidden = true;
          row.classList.add("is-editing");
          row.appendChild(editor);
          textarea.focus();
          textarea.setSelectionRange(textarea.value.length, textarea.value.length);

          const cancelEdit = () => {
            editor.remove();
            message.hidden = false;
            row.classList.remove("is-editing");
          };
          const submitEdit = () => {
            const text = textarea.value.trim();
            if (!text) {
              textarea.focus();
              return;
            }
            sendButton.disabled = true;
            const dispatched = dispatchMessageAction("chat-edit-message-bridge", {
              index: Number(row.dataset.ktemHistoryIndex),
              text,
              files: userMessageFiles(message),
            });
            if (dispatched) {
              cancelEdit();
            } else {
              sendButton.disabled = false;
            }
          };
          cancelButton.addEventListener("click", cancelEdit);
          sendButton.addEventListener("click", submitEdit);
          textarea.addEventListener("keydown", (event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
              event.preventDefault();
              submitEdit();
            }
            if (event.key === "Escape") cancelEdit();
          });
        });

        deleteButton.addEventListener("click", () => {
          if (!window.confirm("确认删除这条问题及对应回答吗？")) return;
          dispatchMessageAction("chat-delete-message-bridge", {
            index: Number(row.dataset.ktemHistoryIndex),
          });
        });

        actionBar.append(copyButton, editButton, deleteButton);
        row.appendChild(actionBar);
      });
    };

    new MutationObserver(enhanceUserMessages).observe(chatbotRoot, {
      characterData: true,
      childList: true,
      subtree: true,
    });
    enhanceUserMessages();
  }

  // Keep navigation and evidence controls on the chat canvas so they remain
  // reachable when either side panel is collapsed.
  const infoExpandButton = document.getElementById("info-expand-button");
  const chatExpandButton = document.getElementById("chat-expand-button");
  const chatColumn = document.getElementById("main-chat-bot");
  const convColumn = document.getElementById("conv-settings-panel");
  if (infoExpandButton) {
    infoExpandButton.title = "显示或隐藏参考证据";
    infoExpandButton.setAttribute("aria-label", "显示或隐藏参考证据");
  }
  if (chatExpandButton) {
    chatExpandButton.title = "显示或隐藏会话列表";
    chatExpandButton.setAttribute("aria-label", "显示或隐藏会话列表");
  }

  // move setting close button
  const settingTabNavBar = document.querySelector("#settings-tab .tab-nav");
  const settingCloseButton = document.getElementById("save-setting-btn");
  if (settingTabNavBar && settingCloseButton) {
    settingTabNavBar.appendChild(settingCloseButton);
  }

  const defaultConvColumnMinWidth = "min(300px, 100%)";
  if (convColumn) convColumn.style.minWidth = defaultConvColumnMinWidth;

  globalThis.toggleChatColumn = () => {
    if (!convColumn) return;
    convColumn.classList.toggle("is-collapsed");
  };

  if (convColumn && window.matchMedia("(max-width: 960px)").matches) {
    convColumn.classList.add("is-collapsed");
  }
  if (window.matchMedia("(max-width: 640px)").matches) {
    const gradioContainer = document.querySelector(".gradio-container");
    if (gradioContainer) gradioContainer.style.padding = "8px";
  }

  if (chatColumn && chatExpandButton) {
    chatColumn.insertBefore(chatExpandButton, chatColumn.firstChild);
  }
  if (chatColumn && infoExpandButton) {
    chatColumn.insertBefore(infoExpandButton, chatColumn.firstChild);
  }

  // move use mind-map checkbox
  const mindmapCheckbox = document.getElementById("use-mindmap-checkbox");
  const citationDropdown = document.getElementById("citation-dropdown");
  const chatSettingPanel = document.getElementById("chat-settings-expand");
  if (chatSettingPanel && mindmapCheckbox) {
    chatSettingPanel.insertBefore(mindmapCheckbox, chatSettingPanel.childNodes[2]);
    if (citationDropdown) {
      chatSettingPanel.insertBefore(citationDropdown, mindmapCheckbox);
    }
  }

  // move share conv checkbox
  const reportDiv = document.querySelector(
    "#report-accordion > div:nth-child(3) > div:nth-child(1)"
  );
  const shareConvCheckbox = document.getElementById("is-public-checkbox");
  if (reportDiv && shareConvCheckbox) {
    reportDiv.insertBefore(shareConvCheckbox, reportDiv.querySelector("button"));
  }

  // create slider toggle
  const suggestionCheckbox = document.getElementById("suggest-chat-checkbox");
  if (suggestionCheckbox) {
    const labelElement = suggestionCheckbox.getElementsByTagName("label")[0];
    const checkboxSpan = suggestionCheckbox.getElementsByTagName("span")[0];
    if (labelElement && checkboxSpan) {
      const switchHandle = document.createElement("div");
      labelElement.classList.add("switch");
      suggestionCheckbox.appendChild(checkboxSpan);
      labelElement.appendChild(switchHandle);
    }
  }

  // clpse
  globalThis.clpseFn = (id) => {
    const obj = document.getElementById("clpse-btn-" + id);
    if (!obj) return;
    obj.classList.toggle("clpse-active");
    const content = obj.nextElementSibling;
    if (!content) return;
    if (content.style.display === "none") {
      content.style.display = "block";
    } else {
      content.style.display = "none";
    }
  };

  // store info in local storage
  globalThis.setStorage = (key, value) => {
    localStorage.setItem(key, value);
  };
  globalThis.getStorage = (key, value) => {
    const item = localStorage.getItem(key);
    return item ? item : value;
  };
  globalThis.removeFromStorage = (key) => {
    localStorage.removeItem(key);
  };

  // Function to scroll to given citation with ID
  // Sleep function using Promise and setTimeout
  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  globalThis.scrollToCitation = async (event) => {
    event.preventDefault();
    const citationId = event.target.getAttribute("id");

    await sleep(100);

    const modal = document.getElementById("pdf-modal");
    const citation = document.querySelector('mark[id="' + citationId + '"]');
    if (!citation) return;

    if (modal && modal.style.display === "block") {
      const details = citation.closest("details");
      const pdfLink = details && details.querySelector(".pdf-link");
      if (pdfLink) pdfLink.click();
    } else {
      citation.scrollIntoView({ behavior: "smooth" });
    }
  };

  const clearSearchHighlights = (root) => {
    root.querySelectorAll("mark[data-ktem-search-highlight]").forEach((mark) => {
      mark.replaceWith(document.createTextNode(mark.textContent || ""));
    });
    root.normalize();
  };

  const highlightText = (container, text) => {
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    let textNode = walker.nextNode();
    while (textNode) {
      const index = textNode.data.indexOf(text);
      if (index >= 0) {
        const matchedNode = textNode.splitText(index);
        matchedNode.splitText(text.length);
        const mark = document.createElement("mark");
        mark.dataset.ktemSearchHighlight = "true";
        matchedNode.replaceWith(mark);
        mark.appendChild(matchedNode);
        return mark;
      }
      textNode = walker.nextNode();
    }
    return null;
  };

  globalThis.fullTextSearch = () => {
    const botMessages = document.querySelectorAll(
      "div#main-chat-bot div.message-row.bot-row"
    );
    const lastBotMessage = botMessages[botMessages.length - 1];
    if (!lastBotMessage || lastBotMessage.classList.contains("text_selection")) {
      return;
    }
    lastBotMessage.classList.add("text_selection");

    const evidences = document.querySelectorAll(
      "#html-info-panel > div:last-child > div > details.evidence div.evidence-content"
    );
    const segmenter = new Intl.Segmenter("zh-CN", { granularity: "sentence" });
    const allSegments = [];
    for (const evidence of evidences) {
      if (!evidence.parentElement.open || evidence.querySelector("div.markmap")) {
        continue;
      }

      const evidenceContent = evidence.textContent.replace(/[\r\n]+/g, " ");
      const sentenceIterator = segmenter.segment(evidenceContent)[Symbol.iterator]();
      let sentence = sentenceIterator.next().value;
      while (sentence) {
        const segment = sentence.segment.trim();
        if (segment) {
          allSegments.push({ id: allSegments.length, text: segment });
        }
        sentence = sentenceIterator.next().value;
      }
    }

    const miniSearch = new MiniSearch({
      fields: ["text"],
      storeFields: ["text"],
    });
    miniSearch.addAll(allSegments);

    lastBotMessage.addEventListener("mouseup", () => {
      const selection = window.getSelection().toString().trim();
      if (!selection) return;
      const results = miniSearch.search(selection);
      if (results.length === 0) return;

      const matchedText = results[0].text;
      const currentEvidences = document.querySelectorAll(
        "#html-info-panel > div:last-child > div > details.evidence div.evidence-content"
      );
      const modal = document.getElementById("pdf-modal");
      currentEvidences.forEach(clearSearchHighlights);

      // Manipulate text nodes only; never reconstruct untrusted evidence HTML.
      for (const evidence of currentEvidences) {
        for (const paragraph of evidence.querySelectorAll("p, li")) {
          const highlight = highlightText(paragraph, matchedText);
          if (!highlight) continue;

          if (modal && modal.style.display === "block") {
            const details = paragraph.closest("details");
            const pdfLink = details && details.querySelector(".pdf-link");
            if (pdfLink) pdfLink.click();
          } else {
            highlight.scrollIntoView({ behavior: "smooth", block: "center" });
          }
          return;
        }
      }
    });
  };

  globalThis.spawnDocument = (content, options) => {
    let opt = {
      window: "",
      closeChild: true,
      childId: "_blank",
    };
    Object.assign(opt, options);
    // minimal error checking
    if (
      content &&
      typeof content.toString == "function" &&
      content.toString().length
    ) {
      let child = window.open("", opt.childId, opt.window);
      child.document.write(content.toString());
      if (opt.closeChild) child.document.close();
      return child;
    }
  };

  globalThis.fillChatInput = (event) => {
    const chatInput = document.querySelector("#chat-input textarea");
    if (!chatInput) return;
    // fill the chat input with the clicked div text
    chatInput.value = "请解释：" + event.target.textContent;
    chatInput.dispatchEvent(new Event("input", { bubbles: true }));
    chatInput.focus();
  };
}

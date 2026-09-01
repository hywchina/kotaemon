function run() {
  // Authentication callbacks run during the initial Gradio load. Define these
  // helpers before optional UI enhancements so a layout error can never hide
  // the login form.
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
    image:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><circle cx="9" cy="10" r="1.5"/><path d="m5.5 17 4.5-4 3.2 2.8 2.3-2 3 3.2"/></svg>',
    file:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.5h7l5 5V20a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z"/><path d="M13 3.5V9h5M8 13h7M8 17h7"/></svg>',
    microphone:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15a3.5 3.5 0 0 0 3.5-3.5v-5a3.5 3.5 0 1 0-7 0v5A3.5 3.5 0 0 0 12 15Z"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M9 21h6"/></svg>',
    send:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M6.5 10.5 12 5l5.5 5.5"/></svg>',
    close:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>',
    check:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
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

  // Rebuild the composer shell around Gradio's native inputs. The native file
  // and audio controls still own browser permissions and backend events, while
  // this stable layer provides the compact interaction shown to users.
  const composerRow = document.getElementById("chat-composer-row");
  const chatInput = document.getElementById("chat-input");
  if (composerRow && chatInput) {
    let attachmentMenu = composerRow.querySelector(".ktem-attachment-menu");
    if (!attachmentMenu) {
      attachmentMenu = document.createElement("div");
      attachmentMenu.className = "ktem-attachment-menu";
      attachmentMenu.setAttribute("role", "menu");
      attachmentMenu.innerHTML =
        '<button type="button" role="menuitem" data-ktem-upload="image">' +
        icon.image +
        '<span>添加图片</span></button>' +
        '<button type="button" role="menuitem" data-ktem-upload="file">' +
        icon.file +
        '<span>添加文件</span></button>';
      composerRow.appendChild(attachmentMenu);
    }

    let composerNotice = composerRow.querySelector(".ktem-composer-notice");
    if (!composerNotice) {
      composerNotice = document.createElement("div");
      composerNotice.className = "ktem-composer-notice";
      composerNotice.setAttribute("role", "status");
      composerNotice.setAttribute("aria-live", "polite");
      composerRow.appendChild(composerNotice);
    }

    const showComposerNotice = (message) => {
      window.clearTimeout(composerNotice.ktemHideTimer);
      composerNotice.textContent = message;
      composerNotice.classList.add("is-visible");
      composerNotice.ktemHideTimer = window.setTimeout(() => {
        composerNotice.classList.remove("is-visible");
      }, 3600);
    };

    const acceptedExtensions = (input, fallback) => {
      const accept = (input?.getAttribute("accept") || "")
        .split(",")
        .map((item) => item.trim().toLowerCase())
        .filter((item) => item.startsWith("."));
      return new Set(accept.length ? accept : fallback);
    };

    const bindUploadValidation = (input, fallbackExtensions, message) => {
      if (!input || input.dataset.ktemTypeValidation) return;
      input.dataset.ktemTypeValidation = "true";
      input.addEventListener(
        "change",
        (event) => {
          const allowed = acceptedExtensions(input, fallbackExtensions);
          const invalidFile = Array.from(input.files || []).find((file) => {
            const normalizedName = file.name.toLowerCase();
            return !Array.from(allowed).some((extension) =>
              normalizedName.endsWith(extension)
            );
          });
          if (!invalidFile) return;
          event.preventDefault();
          event.stopImmediatePropagation();
          input.value = "";
          showComposerNotice(`不支持“${invalidFile.name}”。${message}`);
        },
        true
      );
    };
    const imageExtensions = [".png", ".jpg", ".jpeg", ".webp"];
    const documentExtensions = [
      ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".pptx",
      ".txt", ".md", ".html", ".mhtml", ".png", ".jpg",
      ".jpeg", ".tif", ".tiff"
    ];
    const imageTypeMessage = "图片仅支持 PNG、JPEG 和 WebP 格式。";
    const documentTypeMessage = "请选择系统支持的文档或图片格式。";

    let microphoneButton = composerRow.querySelector(".ktem-microphone-trigger");
    if (!microphoneButton) {
      microphoneButton = document.createElement("button");
      microphoneButton.type = "button";
      microphoneButton.className = "ktem-microphone-trigger";
      microphoneButton.innerHTML = icon.microphone;
      microphoneButton.title = "开始实时语音转写";
      microphoneButton.setAttribute("aria-label", "开始实时语音转写");
      composerRow.appendChild(microphoneButton);
    }

    let recorder = composerRow.querySelector(".ktem-inline-recorder");
    if (!recorder) {
      recorder = document.createElement("div");
      recorder.className = "ktem-inline-recorder";
      recorder.setAttribute("aria-label", "正在录音");
      const bars = Array.from({ length: 72 }, (_, index) => {
        const height = 5 + ((index * 11 + index * index) % 18);
        const delay = -((index % 13) * 0.05).toFixed(2);
        return `<i style="--bar-height:${height}px;--bar-delay:${delay}s"></i>`;
      }).join("");
      recorder.innerHTML =
        '<div class="ktem-recorder-lead" aria-hidden="true"></div>' +
        `<div class="ktem-recorder-wave" aria-hidden="true">${bars}</div>`;
      composerRow.appendChild(recorder);
    }

    const closeAttachmentMenu = () => {
      attachmentMenu.classList.remove("is-open");
      composerRow.classList.remove("has-attachment-menu");
      const uploadButton = chatInput.querySelector(
        "button[data-testid='upload-button']"
      );
      if (uploadButton) uploadButton.setAttribute("aria-expanded", "false");
    };

    const audioRoot = document.getElementById("asr-live-audio");
    const cancelBridge = document.getElementById("asr-cancel-bridge");
    const confirmBridge = document.getElementById("asr-confirm-bridge");
    const cancelBridgeButton = resolveButton(cancelBridge);
    const confirmBridgeButton = resolveButton(confirmBridge);
    if (cancelBridgeButton) {
      cancelBridgeButton.classList.add("ktem-recorder-cancel");
      setIconButton(cancelBridgeButton, icon.close, "取消录音");
      if (!recorder.contains(cancelBridgeButton)) {
        recorder.appendChild(cancelBridgeButton);
      }
    }
    if (confirmBridgeButton) {
      confirmBridgeButton.classList.add("ktem-recorder-confirm");
      setIconButton(confirmBridgeButton, icon.check, "完成录音");
      if (!recorder.contains(confirmBridgeButton)) {
        recorder.appendChild(confirmBridgeButton);
      }
    }
    composerRow.classList.toggle("has-live-audio", Boolean(audioRoot));
    const nativeRecordButton = () =>
      audioRoot && audioRoot.querySelector("button.record-button");
    const nativeStopButton = () =>
      audioRoot && audioRoot.querySelector("button.stop-button");

    const syncRecordingUi = () => {
      const hasNativeStopButton = Boolean(nativeStopButton());
      if (!hasNativeStopButton) delete composerRow.dataset.ktemAsrEnding;
      const recording =
        hasNativeStopButton && !composerRow.dataset.ktemAsrEnding;
      composerRow.classList.toggle("is-asr-recording", recording);
      document.body.classList.toggle("ktem-asr-recording", recording);
      const textarea = chatInput.querySelector("textarea");
      if (textarea) textarea.readOnly = recording;
      if (recording) closeAttachmentMenu();
    };

    const beginRecording = () => {
      const recordButton = nativeRecordButton();
      if (!recordButton) return;
      delete composerRow.dataset.ktemAsrEnding;
      closeAttachmentMenu();
      composerRow.classList.add("is-asr-recording");
      document.body.classList.add("ktem-asr-recording");
      recordButton.click();
      setTimeout(syncRecordingUi, 250);
      setTimeout(syncRecordingUi, 3000);
    };

    const endRecording = (mode) => {
      composerRow.dataset.ktemAsrEnding = mode;
      const stopButton = nativeStopButton();
      window.setTimeout(() => {
        if (stopButton) stopButton.click();
      }, 0);
      composerRow.classList.remove("is-asr-recording");
      document.body.classList.remove("ktem-asr-recording");
      const textarea = chatInput.querySelector("textarea");
      if (textarea) textarea.readOnly = false;
    };

    if (!microphoneButton.dataset.ktemBound) {
      microphoneButton.dataset.ktemBound = "true";
      microphoneButton.addEventListener("click", beginRecording);
    }
    if (cancelBridgeButton && !cancelBridgeButton.dataset.ktemRecorderBound) {
      cancelBridgeButton.dataset.ktemRecorderBound = "true";
      cancelBridgeButton.addEventListener("click", () => endRecording("cancel"));
    }
    if (confirmBridgeButton && !confirmBridgeButton.dataset.ktemRecorderBound) {
      confirmBridgeButton.dataset.ktemRecorderBound = "true";
      confirmBridgeButton.addEventListener("click", () => endRecording("confirm"));
    }

    if (audioRoot && !audioRoot.dataset.ktemObserved) {
      audioRoot.dataset.ktemObserved = "true";
      new MutationObserver(syncRecordingUi).observe(audioRoot, {
        childList: true,
        subtree: true,
      });
    }

    if (!document.body.dataset.ktemAttachmentDismiss) {
      document.body.dataset.ktemAttachmentDismiss = "true";
      document.addEventListener("click", (event) => {
        if (!composerRow.contains(event.target)) closeAttachmentMenu();
      });
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeAttachmentMenu();
      });
    }

    if (!attachmentMenu.dataset.ktemBound) {
      attachmentMenu.dataset.ktemBound = "true";
      attachmentMenu
        .querySelector('[data-ktem-upload="image"]')
        .addEventListener("click", () => {
          closeAttachmentMenu();
          const imageInput = chatInput.querySelector('input[type="file"]');
          if (imageInput) {
            bindUploadValidation(
              imageInput,
              imageExtensions,
              imageTypeMessage
            );
            imageInput.click();
          } else {
            showComposerNotice("图片上传组件尚未就绪，请稍后重试。");
          }
        });
      attachmentMenu
        .querySelector('[data-ktem-upload="file"]')
        .addEventListener("click", () => {
          closeAttachmentMenu();
          const fileInput = document.querySelector(
            '#quick-file input[type="file"]'
          );
          if (fileInput) {
            bindUploadValidation(
              fileInput,
              documentExtensions,
              documentTypeMessage
            );
            fileInput.click();
          } else {
            showComposerNotice("文件上传组件尚未就绪，请稍后重试。");
          }
        });
    }

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
        setIconButton(uploadButton, icon.plus, "添加附件");
        uploadButton.setAttribute("aria-haspopup", "menu");
        uploadButton.setAttribute(
          "aria-expanded",
          attachmentMenu.classList.contains("is-open") ? "true" : "false"
        );
        if (!uploadButton.dataset.ktemMenuBound) {
          uploadButton.dataset.ktemMenuBound = "true";
          uploadButton.addEventListener(
            "click",
            (event) => {
              event.preventDefault();
              event.stopImmediatePropagation();
              const willOpen = !attachmentMenu.classList.contains("is-open");
              closeAttachmentMenu();
              if (willOpen) {
                attachmentMenu.classList.add("is-open");
                composerRow.classList.add("has-attachment-menu");
                uploadButton.setAttribute("aria-expanded", "true");
              }
            },
            true
          );
        }
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
      const hasFiles = Boolean(chatInput.querySelector(".thumbnail-item"));
      composerRow.classList.remove("has-expanded-text");
      const hasExpandedText = Boolean(
        textarea && textarea.value.trim() && textarea.scrollHeight > 80
      );
      composerRow.classList.toggle(
        "has-expanded-text",
        hasExpandedText && !hasFiles
      );
      composerRow.classList.toggle("has-attachments", hasFiles);
      composerRow.classList.toggle("has-message-content", hasText || hasFiles);
      if (sendButton) {
        sendButton.disabled = !(hasText || hasFiles);
        sendButton.setAttribute(
          "aria-disabled",
          hasText || hasFiles ? "false" : "true"
        );
      }
      const quickFileInput = document.querySelector(
        '#quick-file input[type="file"]'
      );
      const imageFileInput = chatInput.querySelector('input[type="file"]');
      bindUploadValidation(
        imageFileInput,
        imageExtensions,
        imageTypeMessage
      );
      bindUploadValidation(
        quickFileInput,
        documentExtensions,
        documentTypeMessage
      );
      const fileMenuButton = attachmentMenu.querySelector(
        '[data-ktem-upload="file"]'
      );
      if (fileMenuButton) fileMenuButton.disabled = !quickFileInput;
      microphoneButton.hidden = !audioRoot;
      syncRecordingUi();
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

  // Move the public-conversation toggle into the feedback form. It originally
  // shares a narrow toolbar with the suggestion toggle and three icon buttons;
  // leaving it there makes both labels collapse vertically in the sidebar.
  const feedbackSubmitContent = document.querySelector(
    "#feedback-submit-panel > div:nth-child(3) > div:nth-child(1)"
  );
  const feedbackSubmitButton = document.getElementById("feedback-submit-button");
  const shareConvCheckbox = document.getElementById("is-public-checkbox");
  if (
    feedbackSubmitContent &&
    feedbackSubmitButton &&
    shareConvCheckbox &&
    feedbackSubmitButton.parentNode === feedbackSubmitContent
  ) {
    feedbackSubmitContent.insertBefore(shareConvCheckbox, feedbackSubmitButton);
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
      if (!child) return null;
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

function run() {
  let main_parent = document.getElementById("chat-tab").parentNode;

  main_parent.childNodes[0].classList.add("header-bar");
  main_parent.style = "padding: 0; margin: 0";
  main_parent.parentNode.style = "gap: 0";
  main_parent.parentNode.parentNode.style = "padding: 0";

  const version_node = document.createElement("p");
  version_node.innerHTML = "version: KH_APP_VERSION";
  version_node.style = "position: fixed; top: 10px; right: 10px;";
  main_parent.appendChild(version_node);

  // add favicon
  const favicon = document.createElement("link");
  // set favicon attributes
  favicon.rel = "icon";
  favicon.type = "image/svg+xml";
  favicon.href = "/favicon.ico";
  document.head.appendChild(favicon);

  // setup conversation dropdown placeholder
  let conv_dropdown = document.querySelector("#conversation-dropdown input");
  conv_dropdown.placeholder = "浏览会话记录";  // translate Browse conversation --》浏览对话记录

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
      if (sendButton && sendButton.disabled === (hasText || hasFiles)) {
        sendButton.disabled = !(hasText || hasFiles);
      }
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
    if (!payloadInput || !bridgeButton) return;

    payloadInput.value = JSON.stringify(payload);
    payloadInput.dispatchEvent(new Event("input", { bubbles: true }));
    payloadInput.dispatchEvent(new Event("change", { bubbles: true }));
    bridgeButton.click();
  };

  // Gradio does not render a stable action bar for user messages across versions,
  // so attach a dedicated copy/edit/delete bar to every user-side row.
  const chatbotRoot = document.getElementById("main-chat-bot");
  if (chatbotRoot) {
    const enhanceUserMessages = () => {
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
          const text = message ? message.innerText.trim() : "";
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
          textarea.value = message.innerText.trim();
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
            dispatchMessageAction("chat-edit-message-bridge", {
              index: Number(row.dataset.ktemHistoryIndex),
              text,
            });
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
      childList: true,
      subtree: true,
    });
    enhanceUserMessages();
  }

  // move info-expand-button
  let info_expand_button = document.getElementById("info-expand-button");
  let chat_info_panel = document.getElementById("info-expand");
  chat_info_panel.insertBefore(
    info_expand_button,
    chat_info_panel.childNodes[2]
  );

  // move toggle-side-bar button
  let chat_expand_button = document.getElementById("chat-expand-button");
  let chat_column = document.getElementById("main-chat-bot");
  let conv_column = document.getElementById("conv-settings-panel");

  // move setting close button
  let setting_tab_nav_bar = document.querySelector("#settings-tab .tab-nav");
  let setting_close_button = document.getElementById("save-setting-btn");
  if (setting_close_button) {
    setting_tab_nav_bar.appendChild(setting_close_button);
  }

  let default_conv_column_min_width = "min(300px, 100%)";
  conv_column.style.minWidth = default_conv_column_min_width;

  globalThis.toggleChatColumn = () => {
    /* get flex-grow value of chat_column */
    let flex_grow = conv_column.style.flexGrow;
    if (flex_grow == "0") {
      conv_column.style.flexGrow = "1";
      conv_column.style.minWidth = default_conv_column_min_width;
    } else {
      conv_column.style.flexGrow = "0";
      conv_column.style.minWidth = "0px";
    }
  };

  chat_column.insertBefore(chat_expand_button, chat_column.firstChild);

  // move use mind-map checkbox
  let mindmap_checkbox = document.getElementById("use-mindmap-checkbox");
  let citation_dropdown = document.getElementById("citation-dropdown");
  let chat_setting_panel = document.getElementById("chat-settings-expand");
  chat_setting_panel.insertBefore(
    mindmap_checkbox,
    chat_setting_panel.childNodes[2]
  );
  chat_setting_panel.insertBefore(citation_dropdown, mindmap_checkbox);

  // move share conv checkbox
  let report_div = document.querySelector(
    "#report-accordion > div:nth-child(3) > div:nth-child(1)"
  );
  let share_conv_checkbox = document.getElementById("is-public-checkbox");
  if (share_conv_checkbox) {
    report_div.insertBefore(share_conv_checkbox, report_div.querySelector("button"));
  }

  // create slider toggle
  const is_public_checkbox = document.getElementById("suggest-chat-checkbox");
  const label_element = is_public_checkbox.getElementsByTagName("label")[0];
  const checkbox_span = is_public_checkbox.getElementsByTagName("span")[0];
  new_div = document.createElement("div");

  label_element.classList.add("switch");
  is_public_checkbox.appendChild(checkbox_span);
  label_element.appendChild(new_div);

  // clpse
  globalThis.clpseFn = (id) => {
    var obj = document.getElementById("clpse-btn-" + id);
    obj.classList.toggle("clpse-active");
    var content = obj.nextElementSibling;
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
    item = localStorage.getItem(key);
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
    event.preventDefault(); // Prevent the default link behavior
    var citationId = event.target.getAttribute("id");

    await sleep(100); // Sleep for 100 milliseconds

    // check if modal is open
    var modal = document.getElementById("pdf-modal");
    var citation = document.querySelector('mark[id="' + citationId + '"]');

    if (modal.style.display == "block") {
      // trigger on click event of PDF Preview link
      var detail_elem = citation;
      // traverse up the DOM tree to find the parent element with tag detail
      while (detail_elem.tagName.toLowerCase() != "details") {
        detail_elem = detail_elem.parentElement;
      }
      detail_elem.getElementsByClassName("pdf-link").item(0).click();
    } else {
      if (citation) {
        citation.scrollIntoView({ behavior: "smooth" });
      }
    }
  };

  globalThis.fullTextSearch = () => {
    // Assign text selection event to last bot message
    var bot_messages = document.querySelectorAll(
      "div#main-chat-bot div.message-row.bot-row"
    );
    var last_bot_message = bot_messages[bot_messages.length - 1];

    // check if the last bot message has class "text_selection"
    if (last_bot_message.classList.contains("text_selection")) {
      return;
    }

    // assign new class to last message
    last_bot_message.classList.add("text_selection");

    // Get sentences from evidence div
    var evidences = document.querySelectorAll(
      "#html-info-panel > div:last-child > div > details.evidence div.evidence-content"
    );
    console.log("Indexing evidences", evidences);

    const segmenterEn = new Intl.Segmenter("en", { granularity: "sentence" });
    // Split sentences and save to all_segments list
    var all_segments = [];
    for (var evidence of evidences) {
      // check if <details> tag is open
      if (!evidence.parentElement.open) {
        continue;
      }
      var markmap_div = evidence.querySelector("div.markmap");
      if (markmap_div) {
        continue;
      }

      var evidence_content = evidence.textContent.replace(/[\r\n]+/g, " ");
      sentence_it = segmenterEn.segment(evidence_content)[Symbol.iterator]();
      while ((sentence = sentence_it.next().value)) {
        segment = sentence.segment.trim();
        if (segment) {
          all_segments.push({
            id: all_segments.length,
            text: segment,
          });
        }
      }
    }

    let miniSearch = new MiniSearch({
      fields: ["text"], // fields to index for full-text search
      storeFields: ["text"],
    });

    // Index all documents
    miniSearch.addAll(all_segments);

    last_bot_message.addEventListener("mouseup", () => {
      let selection = window.getSelection().toString();
      let results = miniSearch.search(selection);

      if (results.length == 0) {
        return;
      }
      let matched_text = results[0].text;
      console.log("query\n", selection, "\nmatched text\n", matched_text);

      var evidences = document.querySelectorAll(
        "#html-info-panel > div:last-child > div > details.evidence div.evidence-content"
      );
      // check if modal is open
      var modal = document.getElementById("pdf-modal");

      // convert all <mark> in evidences to normal text
      evidences.forEach((evidence) => {
        evidence.querySelectorAll("mark").forEach((mark) => {
          mark.outerHTML = mark.innerText;
        });
      });

      // highlight matched_text in evidences
      for (var evidence of evidences) {
        var evidence_content = evidence.textContent.replace(/[\r\n]+/g, " ");
        if (evidence_content.includes(matched_text)) {
          // select all p and li elements
          paragraphs = evidence.querySelectorAll("p, li");
          for (var p of paragraphs) {
            var p_content = p.textContent.replace(/[\r\n]+/g, " ");
            if (p_content.includes(matched_text)) {
              p.innerHTML = p_content.replace(
                matched_text,
                "<mark>" + matched_text + "</mark>"
              );
              console.log("highlighted", matched_text, "in", p);
              if (modal.style.display == "block") {
                // trigger on click event of PDF Preview link
                var detail_elem = p;
                // traverse up the DOM tree to find the parent element with tag detail
                while (detail_elem.tagName.toLowerCase() != "details") {
                  detail_elem = detail_elem.parentElement;
                }
                detail_elem.getElementsByClassName("pdf-link").item(0).click();
              } else {
                p.scrollIntoView({ behavior: "smooth", block: "center" });
              }
              break;
            }
          }
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
    let chatInput = document.querySelector("#chat-input textarea");
    // fill the chat input with the clicked div text
    chatInput.value = "Explain " + event.target.textContent;
    var evt = new Event("change");
    chatInput.dispatchEvent(new Event("input", { bubbles: true }));
    chatInput.focus();
  };
}

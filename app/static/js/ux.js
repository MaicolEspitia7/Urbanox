(() => {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Catalog dock: se queda fijo al bajar a ver prendas
  const catalogDock = document.querySelector("[data-catalog-dock]");
  const catalogSentinel = document.querySelector("[data-catalog-dock-sentinel]");
  const catalogSpacer = document.querySelector("[data-catalog-dock-spacer]");
  if (catalogDock && catalogSentinel) {
    const syncPinned = (pinned) => {
      catalogDock.classList.toggle("is-pinned", pinned);
      if (catalogSpacer) {
        catalogSpacer.classList.toggle("is-on", pinned);
        catalogSpacer.style.height = pinned ? `${catalogDock.offsetHeight}px` : "0px";
      }
    };
    const headerOffset = window.matchMedia("(max-width: 720px)").matches ? 58 : 64;
    const observer = new IntersectionObserver(
      ([entry]) => {
        syncPinned(!entry.isIntersecting);
      },
      { threshold: 0, rootMargin: `-${headerOffset}px 0px 0px 0px` }
    );
    observer.observe(catalogSentinel);
    window.addEventListener("resize", () => {
      if (catalogDock.classList.contains("is-pinned") && catalogSpacer) {
        catalogSpacer.style.height = `${catalogDock.offsetHeight}px`;
      }
    });
  }

  // Cinematic intro (once per session)
  const intro = document.querySelector("[data-intro]");
  if (intro) {
    const seen = sessionStorage.getItem("urbanox-intro") === "1";
    if (seen || reduceMotion) {
      intro.remove();
    } else {
      intro.removeAttribute("aria-hidden");
      window.setTimeout(() => {
        intro.classList.add("is-done");
        sessionStorage.setItem("urbanox-intro", "1");
        window.setTimeout(() => intro.remove(), 750);
      }, 1600);
    }
  }

  // Gold spotlight that follows the cursor
  if (!reduceMotion && window.matchMedia("(pointer:fine)").matches) {
    let raf = 0;
    let targetX = 50;
    let targetY = 30;
    let currentX = 50;
    let currentY = 30;

    const tick = () => {
      currentX += (targetX - currentX) * 0.08;
      currentY += (targetY - currentY) * 0.08;
      document.documentElement.style.setProperty("--spot-x", `${currentX}%`);
      document.documentElement.style.setProperty("--spot-y", `${currentY}%`);
      raf = window.requestAnimationFrame(tick);
    };

    window.addEventListener(
      "pointermove",
      (event) => {
        targetX = (event.clientX / window.innerWidth) * 100;
        targetY = (event.clientY / window.innerHeight) * 100;
      },
      { passive: true },
    );
    raf = window.requestAnimationFrame(tick);
  }

  // Scroll reveals
  const revealNodes = Array.from(document.querySelectorAll(".reveal-on-scroll"));
  if (revealNodes.length) {
    if (reduceMotion || !("IntersectionObserver" in window)) {
      revealNodes.forEach((node) => node.classList.add("is-in"));
    } else {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-in");
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.18, rootMargin: "0px 0px -8% 0px" },
      );
      revealNodes.forEach((node) => observer.observe(node));
    }
  }

  // Toast flashes (avisos bacanos)
  const flashes = Array.from(document.querySelectorAll(".flash"));
  if (flashes.length) {
    let host = document.querySelector(".toast-host");
    if (!host) {
      host = document.createElement("div");
      host.className = "toast-host";
      host.setAttribute("aria-live", "polite");
      document.body.appendChild(host);
    }

    flashes.forEach((flash, index) => {
      const isError = flash.classList.contains("flash-error");
      flash.classList.add("toast", "toast-fx");
      const copy = document.createElement("div");
      copy.className = "toast-copy";
      const badge = document.createElement("span");
      badge.className = "toast-badge";
      badge.textContent = isError ? "!" : "OK";
      const text = document.createElement("p");
      text.className = "toast-text";
      text.textContent = flash.textContent.trim();
      flash.textContent = "";
      copy.append(badge, text);
      flash.appendChild(copy);

      const close = document.createElement("button");
      close.type = "button";
      close.className = "toast-close";
      close.setAttribute("aria-label", "Cerrar aviso");
      close.textContent = "×";
      close.addEventListener("click", () => flash.remove());
      flash.appendChild(close);
      host.appendChild(flash);

      if (!reduceMotion) {
        flash.style.animationDelay = `${index * 80}ms`;
      }

      window.setTimeout(() => {
        flash.classList.add("toast-out");
        window.setTimeout(() => flash.remove(), 320);
      }, 4600 + index * 400);
    });
  }

  // Modal de confirmación Urbanox
  function ensureConfirmModal() {
    let root = document.querySelector("[data-ux-confirm]");
    if (root) return root;

    root = document.createElement("div");
    root.className = "ux-confirm";
    root.setAttribute("data-ux-confirm", "");
    root.hidden = true;
    root.innerHTML = `
      <div class="ux-confirm-backdrop" data-ux-confirm-cancel></div>
      <div class="ux-confirm-card" role="dialog" aria-modal="true" aria-labelledby="ux-confirm-title">
        <div class="ux-confirm-glow" aria-hidden="true"></div>
        <p class="ux-confirm-kicker" data-ux-confirm-kicker>CONFIRMAR</p>
        <h2 id="ux-confirm-title" class="ux-confirm-title" data-ux-confirm-title>¿Confirmás?</h2>
        <p class="ux-confirm-text" data-ux-confirm-text></p>
        <div class="ux-confirm-actions">
          <button type="button" class="btn btn-ghost" data-ux-confirm-cancel>Cancelar</button>
          <button type="button" class="btn btn-accent ux-confirm-ok" data-ux-confirm-ok>Confirmar</button>
        </div>
      </div>
    `;
    document.body.appendChild(root);
    return root;
  }

  function askConfirm({ title, message, okLabel, tone }) {
    const root = ensureConfirmModal();
    const titleEl = root.querySelector("[data-ux-confirm-title]");
    const textEl = root.querySelector("[data-ux-confirm-text]");
    const kickerEl = root.querySelector("[data-ux-confirm-kicker]");
    const okBtn = root.querySelector("[data-ux-confirm-ok]");
    const cancelNodes = root.querySelectorAll("[data-ux-confirm-cancel]");

    titleEl.textContent = title || "¿Confirmás esta acción?";
    textEl.textContent = message || "";
    textEl.hidden = !message;
    kickerEl.textContent = tone === "danger" ? "ATENCIÓN" : "CONFIRMAR";
    okBtn.textContent = okLabel || "Confirmar";
    root.classList.toggle("is-danger", tone === "danger");
    root.hidden = false;
    document.body.classList.add("ux-confirm-open");
    window.setTimeout(() => okBtn.focus(), 30);

    return new Promise((resolve) => {
      const finish = (value) => {
        root.hidden = true;
        document.body.classList.remove("ux-confirm-open");
        root.classList.remove("is-danger");
        cancelNodes.forEach((node) => node.removeEventListener("click", onCancel));
        okBtn.removeEventListener("click", onOk);
        document.removeEventListener("keydown", onKey);
        resolve(value);
      };
      const onCancel = () => finish(false);
      const onOk = () => finish(true);
      const onKey = (event) => {
        if (event.key === "Escape") finish(false);
        if (event.key === "Enter") finish(true);
      };
      cancelNodes.forEach((node) => node.addEventListener("click", onCancel));
      okBtn.addEventListener("click", onOk);
      document.addEventListener("keydown", onKey);
    });
  }

  // Inventory live search
  const inventorySearch = document.querySelector("[data-inventory-search]");
  const inventoryRows = Array.from(document.querySelectorAll("[data-inventory-row]"));
  const inventoryEmpty = document.querySelector("[data-inventory-empty]");
  const inventoryCount = document.querySelector("[data-inventory-count]");

  function filterInventory() {
    if (!inventorySearch) return;
    const term = inventorySearch.value.trim().toLowerCase();
    let visible = 0;
    inventoryRows.forEach((row) => {
      const hay = (row.getAttribute("data-search") || "").toLowerCase();
      const show = !term || hay.includes(term);
      row.hidden = !show;
      if (show) visible += 1;
    });
    if (inventoryEmpty) inventoryEmpty.hidden = visible > 0;
    if (inventoryCount) {
      inventoryCount.textContent = term
        ? `${visible} resultado${visible === 1 ? "" : "s"}`
        : `${inventoryRows.length} prenda${inventoryRows.length === 1 ? "" : "s"}`;
    }
  }

  if (inventorySearch) {
    inventorySearch.addEventListener("input", filterInventory);
    filterInventory();
  }

  // Source segmented control
  const sourceInput = document.querySelector("#source");
  const providerField = document.querySelector("#provider-field");
  const sourceButtons = Array.from(document.querySelectorAll("[data-source-option]"));

  function syncProvider() {
    if (!sourceInput || !providerField) return;
    const isProvider = sourceInput.value === "PROVIDER";
    providerField.hidden = !isProvider;
    const providerInput = providerField.querySelector("input");
    if (providerInput) providerInput.required = isProvider;
    sourceButtons.forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.sourceOption === sourceInput.value);
    });
  }

  sourceButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!sourceInput) return;
      sourceInput.value = btn.dataset.sourceOption;
      syncProvider();
    });
  });
  syncProvider();

  // Image preview + foco / encuadre
  const imageInput = document.querySelector("[data-image-url]");
  const imageFile = document.querySelector("[data-image-file]");
  const imageFilename = document.querySelector("[data-image-filename]");
  const imagePreview = document.querySelector("[data-image-preview]");
  const imageFallback = document.querySelector("[data-image-fallback]");
  const nameInput = document.querySelector("[data-product-name]");
  const focusFrame = document.querySelector("[data-focus-frame]");
  const focusPin = document.querySelector("[data-focus-pin]");
  const focusXInput = document.querySelector("[data-focus-x]");
  const focusYInput = document.querySelector("[data-focus-y]");
  const focusXRange = document.querySelector("[data-focus-x-range]");
  const focusYRange = document.querySelector("[data-focus-y-range]");
  const focusReset = document.querySelector("[data-focus-reset]");
  let objectUrl = null;
  let draggingFocus = false;

  function showFallback() {
    if (!imagePreview) return;
    imagePreview.hidden = true;
    imagePreview.removeAttribute("src");
    if (imageFallback) imageFallback.hidden = false;
    if (focusFrame) focusFrame.classList.remove("has-image");
  }

  function applyFocus(x, y) {
    const fx = Math.max(0, Math.min(100, Math.round(Number(x) || 50)));
    const fy = Math.max(0, Math.min(100, Math.round(Number(y) || 50)));
    if (focusXInput) focusXInput.value = String(fx);
    if (focusYInput) focusYInput.value = String(fy);
    if (focusXRange) focusXRange.value = String(fx);
    if (focusYRange) focusYRange.value = String(fy);
    if (imagePreview) imagePreview.style.objectPosition = `${fx}% ${fy}%`;
    if (focusPin) {
      focusPin.style.left = `${fx}%`;
      focusPin.style.top = `${fy}%`;
    }
  }

  function showPreview(url) {
    if (!imagePreview || !url) {
      showFallback();
      return;
    }
    imagePreview.hidden = false;
    imagePreview.src = url;
    if (imageFallback) imageFallback.hidden = true;
    if (focusFrame) focusFrame.classList.add("has-image");
    applyFocus(focusXInput?.value || 50, focusYInput?.value || 50);
  }

  function syncImagePreview() {
    if (objectUrl) {
      showPreview(objectUrl);
      return;
    }
    const url = imageInput?.value?.trim() || imagePreview?.getAttribute("src") || "";
    if (!url) {
      showFallback();
      return;
    }
    showPreview(url);
  }

  function focusFromPointer(event) {
    if (!focusFrame) return;
    const rect = focusFrame.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;
    applyFocus(x, y);
  }

  if (imagePreview) {
    imagePreview.addEventListener("error", () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
      showFallback();
    });
  }

  if (imageFile) {
    imageFile.addEventListener("change", () => {
      const file = imageFile.files?.[0];
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
      if (!file) {
        if (imageFilename) imageFilename.textContent = "Ningún archivo elegido";
        syncImagePreview();
        return;
      }
      if (imageFilename) imageFilename.textContent = file.name;
      objectUrl = URL.createObjectURL(file);
      showPreview(objectUrl);
    });
  }

  if (imageInput) {
    imageInput.addEventListener("input", () => {
      if (objectUrl) return;
      syncImagePreview();
    });
  }

  if (nameInput && imageFallback) {
    nameInput.addEventListener("input", () => {
      const letter = (nameInput.value.trim()[0] || "U").toUpperCase();
      imageFallback.textContent = letter;
    });
  }

  if (focusXRange) {
    focusXRange.addEventListener("input", () => {
      applyFocus(focusXRange.value, focusYInput?.value || 50);
    });
  }
  if (focusYRange) {
    focusYRange.addEventListener("input", () => {
      applyFocus(focusXInput?.value || 50, focusYRange.value);
    });
  }
  if (focusReset) {
    focusReset.addEventListener("click", () => applyFocus(50, 50));
  }

  if (focusFrame) {
    focusFrame.addEventListener("pointerdown", (event) => {
      if (!focusFrame.classList.contains("has-image") && imagePreview?.hidden) return;
      draggingFocus = true;
      focusFrame.setPointerCapture?.(event.pointerId);
      focusFromPointer(event);
    });
    focusFrame.addEventListener("pointermove", (event) => {
      if (!draggingFocus) return;
      focusFromPointer(event);
    });
    focusFrame.addEventListener("pointerup", () => {
      draggingFocus = false;
    });
    focusFrame.addEventListener("pointercancel", () => {
      draggingFocus = false;
    });
  }

  syncImagePreview();
  applyFocus(focusXInput?.value || 50, focusYInput?.value || 50);

  // Password visibility
  const togglePass = document.querySelector("[data-toggle-password]");
  const passInput = document.querySelector("[data-password-input]");
  if (togglePass && passInput) {
    togglePass.addEventListener("click", () => {
      const show = passInput.type === "password";
      passInput.type = show ? "text" : "password";
      togglePass.textContent = show ? "Ocultar" : "Mostrar";
      togglePass.setAttribute("aria-pressed", String(show));
    });
  }

  // Confirm delete / sale (modal Urbanox)
  document.querySelectorAll("[data-confirm]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      if (form.dataset.confirmReady === "1") {
        delete form.dataset.confirmReady;
        return;
      }
      event.preventDefault();
      const message = form.getAttribute("data-confirm") || "¿Confirmás esta acción?";
      const ok = await askConfirm({
        title: "¿Seguro que querés continuar?",
        message,
        okLabel: "Sí, confirmar",
        tone: "danger",
      });
      if (!ok) return;
      form.dataset.confirmReady = "1";
      form.requestSubmit();
    });
  });

  function bindQtyForm(form, { isAnnotate }) {
    const qtyInput = form.querySelector("[data-qty-input]");
    const qtyLabel = form.querySelector("[data-qty-label]");
    const totalLabel = form.querySelector("[data-sale-total]");
    const stepper = form.querySelector(".qty-stepper");
    const stockMax = Number(stepper?.dataset.max || form.dataset.stock || 1);
    const returnMax = Number(stepper?.dataset.returnMax || 99);
    const unitPrice = Number(form.dataset.unitPrice || 0);
    const submitBtn = form.querySelector(".sale-submit");
    const noteInput = form.querySelector('input[name="note"], [data-kero-note]');
    const reasonSelect = form.querySelector("[data-kero-reason], select[name='reason']");

    const formatCop = (value) =>
      `$ ${Math.round(value).toLocaleString("es-CO")}`;

    const isReturnReason = () => {
      if (!reasonSelect) return false;
      const opt = reasonSelect.selectedOptions?.[0];
      return opt?.dataset?.return === "1";
    };

    const currentMax = () => (isReturnReason() ? returnMax : Math.max(1, stockMax));

    const setQty = (value) => {
      const max = currentMax();
      const next = Math.min(max, Math.max(1, value));
      if (qtyInput) qtyInput.value = String(next);
      if (qtyLabel) qtyLabel.textContent = String(next);
      if (totalLabel) totalLabel.textContent = formatCop(unitPrice * next);
      document.dispatchEvent(new CustomEvent("urbanox:qty-change", { detail: { form } }));
    };

    const syncAnnotateUi = () => {
      if (!isAnnotate || !submitBtn) return;
      const returning = isReturnReason();
      const max = currentMax();
      if (stepper) stepper.dataset.max = String(max);
      submitBtn.textContent = returning
        ? submitBtn.getAttribute("data-label-in") || "Anotar devolución"
        : submitBtn.getAttribute("data-label-out") || "Anotar salida";
      if (Number(qtyInput?.value || 1) > max) setQty(max);
    };

    form.querySelectorAll("[data-qty-step]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const step = Number(btn.dataset.qtyStep || 0);
        setQty(Number(qtyInput?.value || 1) + step);
      });
    });

    if (reasonSelect && isAnnotate) {
      reasonSelect.addEventListener("change", syncAnnotateUi);
      syncAnnotateUi();
    }

    form.addEventListener("submit", async (event) => {
      if (form.dataset.confirmReady === "1") {
        delete form.dataset.confirmReady;
        return;
      }
      event.preventDefault();

      if (isAnnotate && noteInput && noteInput.value.trim().length < 3) {
        noteInput.focus();
        await askConfirm({
          title: "Falta la anotación",
          message: "Escribí una nota corta (mínimo 3 caracteres).",
          okLabel: "Entendido",
          tone: "danger",
        });
        return;
      }

      if (isAnnotate && !isReturnReason() && stockMax < 1) {
        await askConfirm({
          title: "Sin stock",
          message: "No hay unidades para anotar salida. Usá «Se devolvió» para devolver prendas.",
          okLabel: "Entendido",
          tone: "danger",
        });
        return;
      }

      const qty = Number(qtyInput?.value || 1);
      const total = formatCop(unitPrice * qty);
      const returning = isAnnotate && isReturnReason();
      const template =
        (returning
          ? submitBtn?.getAttribute("data-confirm-in")
          : submitBtn?.getAttribute("data-confirm-out") ||
            submitBtn?.getAttribute("data-confirm-template")) ||
        (isAnnotate
          ? "¿Anotar salida de {qty} prenda(s)?"
          : "¿Registrar salida de {qty} por {total}?");
      const message = template.replace("{qty}", String(qty)).replace("{total}", total);
      const ok = await askConfirm({
        title: isAnnotate
          ? returning
            ? "Confirmar devolución Kero"
            : "Confirmar anotación Kero"
          : "Confirmar salida",
        message,
        okLabel: isAnnotate ? "Sí, anotar" : "Sí, registrar",
        tone: "ok",
      });
      if (!ok) return;
      form.dataset.confirmReady = "1";
      form.requestSubmit();
    });
  }

  document.querySelectorAll("[data-sale-form]").forEach((form) => {
    bindQtyForm(form, { isAnnotate: false });
  });
  document.querySelectorAll("[data-annotate-form]").forEach((form) => {
    bindQtyForm(form, { isAnnotate: true });
  });

  // Employee batch checkout (multi-item, one confirm)
  const batchRoot = document.querySelector("[data-employee-batch]");
  if (batchRoot) {
    const batchForm = batchRoot.querySelector("[data-batch-form]");
    const itemsInput = batchForm?.querySelector("[data-batch-items]");
    const reasonInput = batchForm?.querySelector("[data-batch-reason]");
    const noteInput = batchForm?.querySelector("[data-batch-note]");
    const countEl = batchForm?.querySelector("[data-batch-count]");
    const unitsEl = batchForm?.querySelector("[data-batch-units]");
    const totalEl = batchForm?.querySelector("[data-batch-total]");
    const clearBtn = batchForm?.querySelector("[data-batch-clear]");

    const formatCop = (value) => `$ ${Math.round(value).toLocaleString("es-CO")}`;

    const collectBatch = () => {
      const items = [];
      batchRoot.querySelectorAll("[data-sale-card].is-batched").forEach((card) => {
        const form = card.querySelector("[data-sale-form]");
        if (!form) return;
        const id = Number(card.dataset.productId);
        const qty = Number(form.querySelector("[data-qty-input]")?.value || 1);
        const unitPrice = Number(
          form.querySelector("[data-unit-price-input]")?.value ||
            card.dataset.unitPrice ||
            0
        );
        const stock = Number(card.dataset.stock || 0);
        if (!id || qty < 1 || qty > stock) return;
        items.push({
          id,
          qty,
          unit_price: unitPrice,
          name: card.dataset.productName || "",
        });
      });
      return items;
    };

    const syncBatchDock = () => {
      if (!batchForm) return;
      const items = collectBatch();
      const units = items.reduce((sum, item) => sum + item.qty, 0);
      const total = items.reduce((sum, item) => sum + item.qty * item.unit_price, 0);
      if (itemsInput) itemsInput.value = JSON.stringify(items);
      if (countEl) {
        countEl.textContent = `${items.length} prenda${items.length === 1 ? "" : "s"}`;
      }
      if (unitsEl) unitsEl.textContent = `${units} und.`;
      if (totalEl) totalEl.textContent = formatCop(total);
      batchForm.hidden = items.length === 0;
    };

    batchRoot.querySelectorAll("[data-batch-toggle]").forEach((toggle) => {
      toggle.addEventListener("change", () => {
        const card = toggle.closest("[data-sale-card]");
        if (!card) return;
        card.classList.toggle("is-batched", toggle.checked);
        syncBatchDock();
      });
    });

    document.addEventListener("urbanox:qty-change", (event) => {
      const form = event.detail?.form;
      if (!form || !batchRoot.contains(form)) return;
      syncBatchDock();
    });

    clearBtn?.addEventListener("click", () => {
      batchRoot.querySelectorAll("[data-batch-toggle]").forEach((toggle) => {
        toggle.checked = false;
        toggle.closest("[data-sale-card]")?.classList.remove("is-batched");
      });
      syncBatchDock();
    });

    batchForm?.addEventListener("submit", async (event) => {
      if (batchForm.dataset.confirmReady === "1") {
        delete batchForm.dataset.confirmReady;
        return;
      }
      event.preventDefault();
      const items = collectBatch();
      if (!items.length) {
        syncBatchDock();
        return;
      }

      // Motivo/nota del primer ítem marcado (si abrió “no es venta”)
      const firstCard = batchRoot.querySelector("[data-sale-card].is-batched");
      const firstForm = firstCard?.querySelector("[data-sale-form]");
      if (reasonInput) {
        reasonInput.value = firstForm?.querySelector('select[name="reason"]')?.value || "venta";
      }
      if (noteInput) {
        noteInput.value = firstForm?.querySelector('input[name="note"]')?.value || "";
      }
      if (itemsInput) itemsInput.value = JSON.stringify(items);

      const units = items.reduce((sum, item) => sum + item.qty, 0);
      const total = items.reduce((sum, item) => sum + item.qty * item.unit_price, 0);
      const preview = items
        .slice(0, 4)
        .map((item) => `· ${item.name} ×${item.qty}`)
        .join("\n");
      const extra = items.length > 4 ? `\n· …y ${items.length - 4} más` : "";
      const ok = await askConfirm({
        title: "Confirmar lote",
        message: `Vas a sacar ${items.length} prenda(s), ${units} und. por ${formatCop(total)}:\n${preview}${extra}`,
        okLabel: "Sí, sacar todo",
        tone: "ok",
      });
      if (!ok) return;
      batchForm.dataset.confirmReady = "1";
      batchForm.requestSubmit();
    });

    syncBatchDock();
  }

  // Stagger cards
  if (!reduceMotion) {
    document.querySelectorAll(".grid .card").forEach((card, i) => {
      card.style.setProperty("--delay", `${Math.min(i * 45, 360)}ms`);
      card.classList.add("reveal-card");
    });
    document.querySelectorAll(".shop-grid .shop-card, .snap-item").forEach((card, i) => {
      card.style.setProperty("--delay", `${Math.min(i * 55, 420)}ms`);
      card.style.transitionDelay = card.style.getPropertyValue("--delay");
    });
  }

  // Horizontal snap row drag (desktop)
  document.querySelectorAll("[data-snap-row]").forEach((row) => {
    let isDown = false;
    let startX = 0;
    let scrollLeft = 0;

    row.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "touch") return;
      isDown = true;
      row.classList.add("is-dragging");
      startX = event.pageX - row.offsetLeft;
      scrollLeft = row.scrollLeft;
    });
    row.addEventListener("pointerleave", () => {
      isDown = false;
      row.classList.remove("is-dragging");
    });
    row.addEventListener("pointerup", () => {
      isDown = false;
      row.classList.remove("is-dragging");
    });
    row.addEventListener("pointermove", (event) => {
      if (!isDown) return;
      event.preventDefault();
      const x = event.pageX - row.offsetLeft;
      row.scrollLeft = scrollLeft - (x - startX) * 1.15;
    });
  });
})();

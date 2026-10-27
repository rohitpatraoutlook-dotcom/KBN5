(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  const panel = $("kbn5-profile-panel");
  if (!panel) return;

  const profileBox = $("kbn5-profile-data");
  const addressBox = $("kbn5-profile-addresses");
  const message = $("kbn5-profile-message");

  let profile = null;
  let addresses = [];

  function csrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content ||
      document.querySelector('input[name="csrf_token"]')?.value || "";
  }

  async function request(url, options = {}) {
    const headers = {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(csrfToken() ? { "X-CSRFToken": csrfToken() } : {}),
      ...(options.headers || {})
    };

    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.message || data.error || `Request failed (${response.status})`);
    }
    return data;
  }

  function showMessage(text, error = false) {
    message.textContent = text;
    message.classList.toggle("is-error", error);
    message.classList.toggle("is-success", !error);
  }

  function textElement(tag, text, className) {
    const element = document.createElement(tag);
    element.textContent = text ?? "";
    if (className) element.className = className;
    return element;
  }

  function displayName(data) {
    return data.display_name || data.full_name || data.name ||
      [data.first_name, data.last_name].filter(Boolean).join(" ") ||
      data.username || "KBN5 Customer";
  }

  function renderProfile(data) {
    profileBox.replaceChildren();

    const card = document.createElement("div");
    card.className = "kbn5-profile-user-card";

    const avatar = textElement(
      "div",
      displayName(data).trim().charAt(0).toUpperCase() || "K",
      "kbn5-profile-avatar"
    );

    const identity = document.createElement("div");
    identity.appendChild(textElement("h3", displayName(data)));
    identity.appendChild(textElement("p", data.email || "Email not provided"));
    if (data.phone || data.mobile) {
      identity.appendChild(textElement("p", data.phone || data.mobile));
    }

    card.append(avatar, identity);
    profileBox.appendChild(card);

    const form = document.createElement("form");
    form.id = "kbn5-profile-edit-form";
    form.className = "kbn5-profile-edit-form";

    const fields = [
      { key: "display_name", label: "Display name", value: displayName(data), required: true }
    ];

    fields.forEach(field => {
      const label = textElement("label", field.label);
      const input = document.createElement("input");
      input.name = field.key;
      input.value = field.value;
      input.type = field.type || "text";
      input.autocomplete = "name";
      input.required = Boolean(field.required);
      label.appendChild(input);
      form.appendChild(label);
    });

    const save = textElement("button", "Save profile");
    save.type = "submit";
    save.className = "kbn5-profile-primary";
    form.appendChild(save);

    form.addEventListener("submit", async event => {
      event.preventDefault();
      const payload = Object.fromEntries(new FormData(form).entries());

      try {
        showMessage("Saving profile…");
        // Change this URL if the registered profile blueprint uses another route.
        const result = await request("/api/v1/profile/", {
          method: "PATCH",
          body: JSON.stringify(payload)
        });

        profile = result.user || result.profile || result;
        renderProfile(profile);
        showMessage("Profile saved.");
      } catch (error) {
        showMessage("Could not save profile: " + error.message, true);
      }
    });


    const passwordForm = renderPasswordForm();
    const settings = document.getElementById("kbn5-profile-password-mount");
    (settings || profileBox).appendChild(passwordForm);
  }

  function renderPasswordForm() {
    const form = document.createElement("form");
    form.id = "kbn5-profile-password-form";
    form.className = "kbn5-profile-edit-form";

    const fields = [
      { key: "current_password", label: "Current password", autocomplete: "current-password" },
      { key: "new_password", label: "New password (12+ characters)", autocomplete: "new-password" },
      { key: "confirm_password", label: "Confirm new password", autocomplete: "new-password" }
    ];

    fields.forEach(field => {
      const label = textElement("label", field.label);
      const input = document.createElement("input");
      input.name = field.key;
      input.type = "password";
      input.autocomplete = field.autocomplete;
      input.required = true;
      if (field.key !== "current_password") input.minLength = 12;
      label.appendChild(input);
      form.appendChild(label);
    });

    const submit = textElement("button", "Change password");
    submit.type = "submit";
    submit.className = "kbn5-profile-primary";
    form.appendChild(submit);

    form.addEventListener("submit", async event => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(form).entries());

      if (values.new_password !== values.confirm_password) {
        showMessage("New password and confirmation do not match.", true);
        return;
      }

      if (values.new_password.length < 12) {
        showMessage("New password must contain at least 12 characters.", true);
        return;
      }

      try {
        submit.disabled = true;
        showMessage("Changing password…");
        await request("/api/v1/profile/change-password", {
          method: "POST",
          body: JSON.stringify({
            current_password: values.current_password,
            new_password: values.new_password
          })
        });
        form.reset();
        showMessage("Password changed successfully.");
      } catch (error) {
        showMessage("Could not change password: " + error.message, true);
      } finally {
        submit.disabled = false;
      }
    });

    return form;
  }

  function addressId(address) {
    return String(address.id ?? address.address_id ?? "");
  }

  function addressDescription(address) {
    return [
      address.address_line || address.address_line1 || address.address_line_1 || address.line1,
      address.address_line2 || address.address_line_2 || address.line2,
      address.landmark,
      address.area_name,
      address.city,
      address.state,
      address.pincode || address.postal_code
    ].filter(Boolean).join(", ");
  }


  function renderAddAddressForm() {
    const form = document.createElement("form");
    form.id = "kbn5-profile-new-address-form";
    form.className = "kbn5-profile-edit-form";
    form.hidden = true;

    const fields = [
      { key: "label", label: "Address label", placeholder: "Home / Work" },
      { key: "recipient_name", label: "Recipient name", required: true,
        value: profile ? displayName(profile) : "" },
      { key: "phone", label: "10-digit phone number", required: true,
        type: "tel", pattern: "[0-9]{10}", maxLength: 10 },
      { key: "address_line", label: "House / street / address", required: true },
      { key: "landmark", label: "Landmark (optional)" },
      { key: "area_name", label: "Area / locality", required: true },
      { key: "pincode", label: "6-digit PIN code", required: true,
        inputMode: "numeric", pattern: "[0-9]{6}", maxLength: 6 }
    ];

    fields.forEach(field => {
      const label = textElement("label", field.label);
      const input = document.createElement("input");
      input.name = field.key;
      input.type = field.type || "text";
      input.placeholder = field.placeholder || "";
      input.required = Boolean(field.required);
      if (field.value) input.value = field.value;
      if (field.pattern) input.pattern = field.pattern;
      if (field.maxLength) input.maxLength = field.maxLength;
      if (field.inputMode) input.inputMode = field.inputMode;
      label.appendChild(input);
      form.appendChild(label);
    });

    const defaultLabel = document.createElement("label");
    defaultLabel.className = "kbn5-profile-checkbox-label";
    const defaultInput = document.createElement("input");
    defaultInput.type = "checkbox";
    defaultInput.name = "is_default";
    defaultInput.checked = addresses.length === 0;
    defaultLabel.append(defaultInput, document.createTextNode(" Set as default address"));
    form.appendChild(defaultLabel);

    const submit = textElement("button", "Save address");
    submit.type = "submit";
    submit.className = "kbn5-profile-primary";
    form.appendChild(submit);

    const cancel = textElement("button", "Cancel");
    cancel.type = "button";
    cancel.className = "kbn5-profile-secondary";
    cancel.addEventListener("click", () => { form.hidden = true; });
    form.appendChild(cancel);

    form.addEventListener("submit", async event => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(form).entries());
      const payload = {
        label: values.label.trim(),
        recipient_name: values.recipient_name.trim(),
        phone: values.phone.trim(),
        address_line: values.address_line.trim(),
        landmark: values.landmark.trim(),
        area_name: values.area_name.trim(),
        pincode: values.pincode.trim(),
        is_default: defaultInput.checked
      };

      try {
        submit.disabled = true;
        showMessage("Saving delivery address…");
        await request("/api/v1/addresses/", {
          method: "POST",
          body: JSON.stringify(payload)
        });
        form.reset();
        form.hidden = true;
        await loadAddresses();
        showMessage("Delivery address saved.");
      } catch (error) {
        showMessage("Could not save address: " + error.message, true);
      } finally {
        submit.disabled = false;
      }
    });

    return form;
  }

  function renderAddresses() {
    addressBox.replaceChildren();

    const addForm = renderAddAddressForm();
    addressBox.appendChild(addForm);

    if (!addresses.length) {
      addressBox.appendChild(
        textElement("p", "No saved addresses yet.", "kbn5-profile-empty")
      );
      return;
    }

    addresses.forEach(address => {
      const card = document.createElement("article");
      card.className = "kbn5-profile-address-card";

      const heading = document.createElement("div");
      heading.className = "kbn5-profile-address-heading";

      const title = textElement(
        "strong",
        address.label || address.address_type || "Delivery address"
      );
      const isDefault = Boolean(address.is_default || address.default);
      heading.appendChild(title);

      if (isDefault) {
        heading.appendChild(textElement("span", "Default", "kbn5-default-tag"));
      }

      const description = textElement("p", addressDescription(address));
      card.append(heading, description);

      const actions = document.createElement("div");
      actions.className = "kbn5-profile-address-actions";

      if (!isDefault) {
        const setDefault = textElement("button", "Set as default");
        setDefault.type = "button";
        setDefault.addEventListener("click", () => setDefaultAddress(address));
        actions.appendChild(setDefault);
      }

      const remove = textElement("button", "Remove");
      remove.type = "button";
      remove.className = "kbn5-profile-remove-address";
      remove.addEventListener("click", () => deleteAddress(address));
      actions.appendChild(remove);

      card.appendChild(actions);
      addressBox.appendChild(card);
    });
  }

  async function loadProfile() {
    profileBox.textContent = "Loading account details…";
    try {
      const data = await request("/api/v1/profile/");
      profile = data.user || data.profile || data;
      renderProfile(profile);
    } catch (error) {
      profileBox.replaceChildren();
      profileBox.appendChild(
        textElement("p", "Could not load profile. Sign in if required, then refresh.")
      );
      showMessage("Profile unavailable: " + error.message, true);
    }
  }

  async function loadAddresses() {
    addressBox.textContent = "Loading saved addresses…";
    try {
      const data = await request("/api/v1/addresses/");
      addresses = Array.isArray(data)
        ? data
        : data.addresses || data.items || data.results || [];
      renderAddresses();
    } catch (error) {
      addressBox.replaceChildren();
      addressBox.appendChild(
        textElement("p", "Could not load saved addresses.")
      );
    }
  }

  async function setDefaultAddress(address) {
    const id = addressId(address);
    if (!id) return;

    try {
      showMessage("Updating default address…");
      // Adjust if the backend uses a different default-address route.
      const data = await request(`/api/v1/addresses/${encodeURIComponent(id)}/default`, {
        method: "PATCH",
        body: JSON.stringify({ is_default: true })
      });

      addresses = addresses.map(item => ({
        ...item,
        is_default: addressId(item) === id
      }));

      if (data.address) {
        addresses = addresses.map(item =>
          addressId(item) === id ? { ...item, ...data.address, is_default: true } : item
        );
      }

      renderAddresses();
      showMessage("Default address updated.");
    } catch (error) {
      showMessage("Could not update default address: " + error.message, true);
    }
  }

  async function deleteAddress(address) {
    const id = addressId(address);
    if (!id) return;

    if (!window.confirm("Remove this saved address?")) return;

    try {
      await request(`/api/v1/addresses/${encodeURIComponent(id)}`, {
        method: "DELETE"
      });

      addresses = addresses.filter(item => addressId(item) !== id);
      renderAddresses();
      showMessage("Address removed.");
    } catch (error) {
      showMessage("Could not remove address: " + error.message, true);
    }
  }

  function openPanel() {
    panel.hidden = false;
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    document.body.classList.add("kbn5-profile-open");
    loadProfile();
    loadAddresses();
  }

  function closePanel() {
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    document.body.classList.remove("kbn5-profile-open");
  }

  $("kbn5-profile-add-address").addEventListener("click", () => {
    const form = $("kbn5-profile-new-address-form");
    if (!form) return;
    form.hidden = !form.hidden;
    if (!form.hidden) {
      form.querySelector("input[name='recipient_name']")?.focus();
      form.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  });

  $("kbn5-profile-close").addEventListener("click", closePanel);
  $("kbn5-profile-refresh").addEventListener("click", () => {
    loadProfile();
    loadAddresses();
  });

  $("kbn5-profile-logout").addEventListener("click", async () => {
    if (!window.confirm("Are you sure you want to log out?")) return;

    try {
      // Change this URL if the existing authentication blueprint differs.
      await request("/api/v1/auth/logout/", { method: "POST", body: "{}" });
      window.location.href = "/";
    } catch (error) {
      showMessage("Logout endpoint could not be confirmed: " + error.message, true);
    }
  });

  document.addEventListener("click", event => {
    if (event.target.closest("[data-kbn5-open-profile]")) openPanel();
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closePanel();
  });

  window.KBN5ProfileUI = {
    open: openPanel,
    close: closePanel,
    refresh: () => {
      loadProfile();
      loadAddresses();
    }
  };
})();

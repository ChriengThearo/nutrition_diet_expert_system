document.addEventListener("DOMContentLoaded", () => {
    const permissions = new Set(window.APP_PERMISSIONS || []);

    const hasPermission = (code) => permissions.has(code);

    const showPermissionDenied = (action) => {
        const message = `You have no permission to ${action}.`;
        if (typeof window.showNotification === "function") {
            window.showNotification(message, "danger");
            return;
        }
        alert(message);
    };

    document.addEventListener("click", (event) => {
        const target = event.target.closest("[data-permission]");
        if (!target) return;
        const permission = target.dataset.permission;
        if (!permission || hasPermission(permission)) return;
        event.preventDefault();
        event.stopPropagation();
        const action = target.dataset.action || "perform this action";
        showPermissionDenied(action);
    });

    const pwd = document.querySelector('input[name="password"]');
    if (!pwd) return;

    pwd.addEventListener("input", () => {
        const msg = document.querySelector("#passwordHelp");
        if (!msg) return;

        const v = pwd.value;
        const strong = v.length >= 6;

        msg.textContent = strong
            ? "Password length looks good."
            : "Use at least 6 characters.";
        msg.className = strong ? "form-text text-success" : "form-text text-danger";
    });
});

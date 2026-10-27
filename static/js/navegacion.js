document.addEventListener("DOMContentLoaded", function () {
    var grupos = Array.from(document.querySelectorAll("[data-navegacion-grupo]"));

    function cerrar(grupo, devolverFoco) {
        grupo.open = false;
        var disparador = grupo.querySelector("summary");
        disparador.setAttribute("aria-expanded", "false");
        if (devolverFoco) disparador.focus();
    }

    function abrir(grupo, ultimo) {
        grupos.forEach(function (otro) { if (otro !== grupo) cerrar(otro, false); });
        grupo.open = true;
        grupo.querySelector("summary").setAttribute("aria-expanded", "true");
        var items = grupo.querySelectorAll('[role="menuitem"]');
        if (items.length) items[ultimo ? items.length - 1 : 0].focus();
    }

    grupos.forEach(function (grupo) {
        var disparador = grupo.querySelector("summary");
        var items = Array.from(grupo.querySelectorAll('[role="menuitem"]'));
        items.forEach(function (item) { item.tabIndex = -1; });
        disparador.addEventListener("click", function (evento) {
            evento.preventDefault();
            if (grupo.open) cerrar(grupo, true);
            else abrir(grupo, false);
        });
        grupo.addEventListener("toggle", function () {
            disparador.setAttribute("aria-expanded", String(grupo.open));
        });
        grupo.addEventListener("keydown", function (evento) {
            var indice = items.indexOf(document.activeElement);
            if (evento.target === disparador && (evento.key === "Enter" || evento.key === " ")) {
                evento.preventDefault();
                if (grupo.open) cerrar(grupo, true);
                else abrir(grupo, false);
            } else if (evento.key === "Escape" && grupo.open) {
                evento.preventDefault();
                cerrar(grupo, true);
            } else if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
                evento.preventDefault();
                if (!grupo.open || indice < 0) abrir(grupo, evento.key === "ArrowUp");
                else items[(indice + (evento.key === "ArrowDown" ? 1 : -1) + items.length) % items.length].focus();
            } else if (grupo.open && indice >= 0 && (evento.key === "Home" || evento.key === "End")) {
                evento.preventDefault();
                items[evento.key === "Home" ? 0 : items.length - 1].focus();
            } else if (evento.key === "Tab" && indice >= 0) {
                cerrar(grupo, true);
            }
        });
        grupo.addEventListener("focusout", function (evento) {
            if (evento.relatedTarget && !grupo.contains(evento.relatedTarget)) cerrar(grupo, false);
        });
    });
    document.addEventListener("click", function (evento) {
        grupos.forEach(function (grupo) {
            if (!grupo.contains(evento.target)) cerrar(grupo, false);
        });
    });
});

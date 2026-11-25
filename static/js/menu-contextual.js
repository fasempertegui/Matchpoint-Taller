document.addEventListener("DOMContentLoaded", function () {
    function panelDe(menu) {
        return menu.querySelector(".menu-contextual-opciones, .perfil-menu-opciones");
    }

    function limpiarPosicion(menu) {
        var panel = panelDe(menu);
        if (!panel) return;
        panel.style.position = "";
        panel.style.top = "";
        panel.style.left = "";
        panel.style.right = "";
        panel.style.bottom = "";
    }

    function posicionar(menu) {
        var panel = panelDe(menu);
        var disparador = menu.querySelector("summary");
        if (!panel || !disparador) return;

        var margen = 8;
        var rectDisparador = disparador.getBoundingClientRect();
        panel.style.position = "fixed";
        panel.style.right = "auto";
        panel.style.bottom = "auto";
        panel.style.top = "0px";
        panel.style.left = "0px";

        var rectPanel = panel.getBoundingClientRect();
        var espacioAbajo = window.innerHeight - rectDisparador.bottom - margen;
        var espacioArriba = rectDisparador.top - margen;
        var abrirArriba = espacioAbajo < rectPanel.height + 6 && espacioArriba > espacioAbajo;
        var top = abrirArriba
            ? Math.max(margen, rectDisparador.top - rectPanel.height - 6)
            : Math.min(window.innerHeight - rectPanel.height - margen, rectDisparador.bottom + 6);

        var alinearIzquierda = menu.classList.contains("finanzas-menu");
        var left = alinearIzquierda
            ? rectDisparador.left
            : rectDisparador.right - rectPanel.width;
        left = Math.max(margen, Math.min(window.innerWidth - rectPanel.width - margen, left));

        panel.style.top = Math.round(top) + "px";
        panel.style.left = Math.round(left) + "px";
    }

    function cerrarOtros(excepto) {
        document.querySelectorAll("[data-menu-contextual][open]").forEach(function (menu) {
            if (menu !== excepto) menu.open = false;
        });
    }

    document.addEventListener("toggle", function (evento) {
        var menu = evento.target;
        if (!(menu instanceof Element) || !menu.matches("[data-menu-contextual]")) return;
        var disparador = menu.querySelector("summary");
        if (disparador) disparador.setAttribute("aria-expanded", String(menu.open));
        if (menu.open) {
            cerrarOtros(menu);
            posicionar(menu);
        } else {
            limpiarPosicion(menu);
        }
    }, true);

    document.addEventListener("submit", function (evento) {
        var menu = evento.target.closest && evento.target.closest("[data-menu-contextual]");
        if (menu) menu.open = false;
    });

    document.addEventListener("click", function (evento) {
        document.querySelectorAll("[data-menu-contextual][open]").forEach(function (menu) {
            if (!menu.contains(evento.target)) menu.open = false;
        });
    });

    document.addEventListener("keydown", function (evento) {
        if (evento.key !== "Escape") return;
        document.querySelectorAll("[data-menu-contextual][open]").forEach(function (menu) {
            menu.open = false;
            var disparador = menu.querySelector("summary");
            if (disparador) disparador.focus({ preventScroll: true });
        });
    });

    window.addEventListener("resize", function () {
        document.querySelectorAll("[data-menu-contextual][open]").forEach(posicionar);
    });

    window.addEventListener("scroll", function (evento) {
        document.querySelectorAll("[data-menu-contextual][open]").forEach(function (menu) {
            if (!menu.contains(evento.target)) menu.open = false;
        });
    }, true);
});

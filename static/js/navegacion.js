document.addEventListener("DOMContentLoaded", function () {
    var sidebar = document.getElementById("sidebar");
    if (!sidebar) return;

    var cuerpo = document.body;
    var alternar = document.getElementById("sidebar-alternar");
    var cerrar = document.getElementById("sidebar-cerrar");
    var fondo = document.getElementById("sidebar-fondo");
    var contenido = document.getElementById("contenido-principal");
    var barra = document.getElementById("barra-app");
    var tablet = window.matchMedia("(max-width: 900px)");
    var oculta = false;
    try { oculta = localStorage.getItem("academia.sidebar.oculta") === "1"; } catch (error) { /* La navegación funciona sin almacenamiento local. */ }

    function actualizarBoton() {
        var etiqueta;
        if (tablet.matches) {
            var abierta = cuerpo.classList.contains("sidebar-abierta");
            etiqueta = abierta ? "Cerrar navegación" : "Abrir navegación";
            alternar.setAttribute("aria-expanded", String(abierta));
        } else {
            etiqueta = oculta ? "Mostrar barra lateral" : "Ocultar barra lateral";
            alternar.setAttribute("aria-expanded", String(!oculta));
        }
        alternar.setAttribute("aria-label", etiqueta);
        alternar.dataset.tooltip = etiqueta;
    }

    function cerrarPanel(devolverFoco) {
        cuerpo.classList.remove("sidebar-abierta");
        fondo.inert = true;
        sidebar.removeAttribute("role");
        sidebar.removeAttribute("aria-modal");
        contenido.inert = false;
        barra.inert = false;
        if (devolverFoco) alternar.focus();
        sidebar.inert = tablet.matches || oculta;
        actualizarBoton();
    }

    function abrirPanel() {
        sidebar.inert = false;
        fondo.inert = false;
        cuerpo.classList.add("sidebar-abierta");
        sidebar.setAttribute("role", "dialog");
        sidebar.setAttribute("aria-modal", "true");
        actualizarBoton();
        cerrar.focus();
        contenido.inert = true;
        barra.inert = true;
    }

    function actualizar() {
        cerrarPanel(false);
        cuerpo.classList.toggle("sidebar-oculta", !tablet.matches && oculta);
        sidebar.inert = tablet.matches || oculta;
        actualizarBoton();
    }

    alternar.addEventListener("click", function () {
        if (tablet.matches) {
            abrirPanel();
            return;
        }
        oculta = !oculta;
        try { localStorage.setItem("academia.sidebar.oculta", oculta ? "1" : "0"); } catch (error) { /* La preferencia se conserva durante esta página. */ }
        actualizar();
    });
    cerrar.addEventListener("click", function () { cerrarPanel(true); });
    fondo.addEventListener("click", function () { cerrarPanel(true); });
    sidebar.addEventListener("keydown", function (evento) {
        if (!cuerpo.classList.contains("sidebar-abierta")) return;
        if (evento.key === "Escape") {
            evento.preventDefault();
            cerrarPanel(true);
        } else if (evento.key === "Tab") {
            var elementos = Array.from(sidebar.querySelectorAll("a[href], button:not([disabled])")).filter(function (elemento) { return elemento.getClientRects().length; });
            var primero = elementos[0];
            var ultimo = elementos[elementos.length - 1];
            if (evento.shiftKey && document.activeElement === primero) {
                evento.preventDefault(); ultimo.focus();
            } else if (!evento.shiftKey && document.activeElement === ultimo) {
                evento.preventDefault(); primero.focus();
            }
        }
    });
    tablet.addEventListener("change", actualizar);
    fondo.hidden = false;
    cuerpo.classList.add("sidebar-inicializada");
    actualizar();
    window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () {
            cuerpo.classList.add("sidebar-animada");
        });
    });
});

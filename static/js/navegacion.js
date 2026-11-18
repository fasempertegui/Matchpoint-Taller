document.addEventListener("DOMContentLoaded", function () {
    var sidebar = document.getElementById("sidebar");
    if (!sidebar) return;

    var cuerpo = document.body;
    var abrir = document.getElementById("sidebar-abrir");
    var cerrar = document.getElementById("sidebar-cerrar");
    var plegar = document.getElementById("sidebar-plegar");
    var fondo = document.getElementById("sidebar-fondo");
    var contenido = document.getElementById("contenido-principal");
    var cabecera = document.getElementById("sidebar-cabecera-tablet");
    var tablet = window.matchMedia("(max-width: 900px)");
    var compacta = false;
    try { compacta = localStorage.getItem("academia.sidebar.compacta") === "1"; } catch (error) { /* La navegación funciona sin almacenamiento local. */ }

    function cerrarPanel(devolverFoco) {
        cuerpo.classList.remove("sidebar-abierta");
        fondo.hidden = true;
        abrir.setAttribute("aria-expanded", "false");
        sidebar.removeAttribute("role");
        sidebar.removeAttribute("aria-modal");
        contenido.inert = false;
        cabecera.inert = false;
        if (devolverFoco) abrir.focus();
        sidebar.inert = tablet.matches;
    }

    function actualizar() {
        cerrarPanel(false);
        cuerpo.classList.toggle("sidebar-compacta", !tablet.matches && compacta);
        plegar.setAttribute("aria-expanded", String(!compacta));
        var etiqueta = compacta ? "Expandir barra lateral" : "Contraer barra lateral";
        plegar.setAttribute("aria-label", etiqueta);
        plegar.dataset.tooltip = etiqueta;
    }

    abrir.addEventListener("click", function () {
        sidebar.inert = false;
        cuerpo.classList.add("sidebar-abierta");
        fondo.hidden = false;
        abrir.setAttribute("aria-expanded", "true");
        sidebar.setAttribute("role", "dialog");
        sidebar.setAttribute("aria-modal", "true");
        cerrar.focus();
        contenido.inert = true;
        cabecera.inert = true;
    });
    cerrar.addEventListener("click", function () { cerrarPanel(true); });
    fondo.addEventListener("click", function () { cerrarPanel(true); });
    plegar.addEventListener("click", function () {
        compacta = !compacta;
        try { localStorage.setItem("academia.sidebar.compacta", compacta ? "1" : "0"); } catch (error) { /* La preferencia se conserva durante esta página. */ }
        actualizar();
    });
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
    cuerpo.classList.add("sidebar-inicializada");
    actualizar();
});

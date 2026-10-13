// Configuración de la web. Edita solo lo que necesites.
//
//  api       URL del Worker de Cloudflare que lanza la generación sin exponer ningún token
//            (ver worker/README.md). Si está vacío, el botón "Generar PDF" usa un token de
//            GitHub guardado SOLO en tu navegador, o te lleva a GitHub Actions.
//  repo      repositorio donde vive el workflow.
//  workflow  fichero del workflow que genera y publica el informe.
//  ref       rama que sirve GitHub Pages.
window.SUPERANALYST = {
  api: "",
  repo: "Perez849/SuperAnalyst",
  workflow: "pages.yml",
  ref: "main"
};

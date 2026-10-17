/**
 * Vstupní bod — ES modul (strict). Relativní importy fungují vůči URL tohoto souboru.
 */
import { bootPruvodkaCreateForm } from "./form_app.js?v=20260910-ful-not-facility";

document.addEventListener("DOMContentLoaded", bootPruvodkaCreateForm);

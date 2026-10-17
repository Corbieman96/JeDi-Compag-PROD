from django.core.management.base import BaseCommand

from catalogs.services.suffix_merge import merge_suffix_catalog_rows


class Command(BaseCommand):
    help = (
        "Sloučí dva řádky SuffixCatalog: přesune vazby ze zdroje na cíl a zdroj smaže. "
        "Existují-li SuffixSiteProfile na obou koncovkách, profily se sloučí do cílového (M2M odpadů, doplnění prázdných polí). "
        "Příklad: překlep → opravený text v číselníku."
    )

    def add_arguments(self, parser):
        parser.add_argument("source_pk", type=int, help="PK řádku SuffixCatalog ke zrušení")
        parser.add_argument("target_pk", type=int, help="PK řádku SuffixCatalog, na který se přejde")

    def handle(self, *args, **options):
        src = options["source_pk"]
        tgt = options["target_pk"]
        stats = merge_suffix_catalog_rows(source_pk=src, target_pk=tgt)
        for k, v in stats.items():
            self.stdout.write(f"{k}: {v}")

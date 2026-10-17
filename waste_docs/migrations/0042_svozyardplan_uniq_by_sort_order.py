# Generated manually — stejný řidič může být ve slotu V1 i V2 (různé sort_order).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0041_svoztask_source_waste_suffix_pair"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="svozyarddriverplan",
            name="waste_docs_svozyardplan_uniq_date_subj_drv_kind_vk",
        ),
        migrations.AddConstraint(
            model_name="svozyarddriverplan",
            constraint=models.UniqueConstraint(
                fields=("plan_date", "subject_profile", "row_kind", "vehicle_kind", "sort_order"),
                name="waste_docs_svozyardplan_uniq_date_subj_kind_vk_order",
            ),
        ),
    ]

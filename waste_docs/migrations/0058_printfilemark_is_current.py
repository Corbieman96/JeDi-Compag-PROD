from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0057_yard_svoz_submission_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="printfilemark",
            name="is_current",
            field=models.BooleanField(default=True),
        ),
        migrations.AddIndex(
            model_name="printfilemark",
            index=models.Index(
                fields=["is_current", "drive_date"],
                name="waste_docs__is_curr_7a1b2c_idx",
            ),
        ),
    ]

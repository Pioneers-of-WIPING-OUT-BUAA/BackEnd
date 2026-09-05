from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("se", "0004_rename_init_x_map_x_rename_init_y_map_y_and_more")]
    operations = [
        migrations.AddField(model_name="map", name="resolution", field=models.FloatField(default=0.03)),
    ]

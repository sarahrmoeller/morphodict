# Generated by Django 2.2.5 on 2019-09-27 17:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Inflection",
            fields=[
                ("id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("text", models.CharField(max_length=40)),
                (
                    "lc",
                    models.CharField(
                        choices=[
                            ("NA", "NA"),
                            ("NAD", "NAD"),
                            ("NI", "NI"),
                            ("NID", "NID"),
                            ("VAI", "VAI"),
                            ("VII", "VII"),
                            ("VTA", "VTA"),
                            ("VTI", "VTI"),
                            ("IPC", "IPC"),
                            ("PRON", "PRON"),
                            ("", ""),
                        ],
                        max_length=4,
                    ),
                ),
                (
                    "pos",
                    models.CharField(
                        choices=[
                            ("IPV", "IPV"),
                            ("PRON", "PRON"),
                            ("N", "N"),
                            ("IPC", "IPC"),
                            ("V", "V"),
                            ("", ""),
                        ],
                        max_length=4,
                    ),
                ),
                (
                    "analysis",
                    models.CharField(
                        default="",
                        help_text="fst analysis or the best possible if the source is not analyzable",
                        max_length=50,
                    ),
                ),
                (
                    "is_lemma",
                    models.BooleanField(
                        default=False, help_text="Lemma or non-lemma inflection"
                    ),
                ),
                (
                    "as_is",
                    models.BooleanField(
                        default=False,
                        help_text="Fst can not determine the lemma. Paradigm table will not be shown to the user for this entry",
                    ),
                ),
                (
                    "default_spelling",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alt_spellings",
                        to="API.Inflection",
                    ),
                ),
                (
                    "lemma",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inflections",
                        to="API.Inflection",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="EnglishKeyword",
            fields=[
                ("id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("text", models.CharField(max_length=20)),
                (
                    "lemma",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="English",
                        to="API.Inflection",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Definition",
            fields=[
                ("id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("text", models.CharField(max_length=200)),
                ("sources", models.CharField(max_length=5)),
                (
                    "lemma",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="API.Inflection"
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="inflection",
            index=models.Index(
                fields=["analysis"], name="API_inflect_analysi_ebc4bb_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="inflection",
            index=models.Index(fields=["text"], name="API_inflect_text_03fee4_idx"),
        ),
        migrations.AddIndex(
            model_name="englishkeyword",
            index=models.Index(fields=["text"], name="API_english_text_16bd44_idx"),
        ),
    ]
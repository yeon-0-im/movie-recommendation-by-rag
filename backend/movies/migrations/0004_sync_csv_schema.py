from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('movies', '0003_movie_poster_path'),
    ]

    operations = [
        # 컬럼 이름 변경
        migrations.RenameField('movie', 'title', 'title_ko'),
        migrations.RenameField('movie', 'title_en', 'title_original'),
        migrations.RenameField('movie', 'overview', 'overview_ko'),

        # runtime: "139분" 같은 문자열을 숫자로 정제하면서 IntegerField(null=True)로 변환
        migrations.RunSQL(
            "ALTER TABLE movies_movie ALTER COLUMN runtime DROP NOT NULL; "
            "ALTER TABLE movies_movie ALTER COLUMN runtime TYPE INTEGER "
            "USING NULLIF(regexp_replace(runtime, '[^0-9]', '', 'g'), '')::INTEGER",
            reverse_sql="ALTER TABLE movies_movie ALTER COLUMN runtime TYPE VARCHAR(20)",
        ),

        # TMDB 지표
        migrations.AddField(
            model_name='movie',
            name='tmdb_rating',
            field=models.FloatField(null=True, blank=True, verbose_name='TMDB 평점'),
        ),
        migrations.AddField(
            model_name='movie',
            name='tmdb_votes',
            field=models.IntegerField(null=True, blank=True, verbose_name='TMDB 투표수'),
        ),
        migrations.AddField(
            model_name='movie',
            name='tmdb_popularity',
            field=models.FloatField(null=True, blank=True, verbose_name='TMDB 인기도'),
        ),
        migrations.AddField(
            model_name='movie',
            name='audience_kr',
            field=models.IntegerField(null=True, blank=True, verbose_name='국내 누적 관객수'),
        ),

        # 수집 메타
        migrations.AddField(
            model_name='movie',
            name='source_lists',
            field=models.TextField(blank=True, verbose_name='출처 리스트'),
        ),
        migrations.AddField(
            model_name='movie',
            name='list_count',
            field=models.IntegerField(default=0, verbose_name='등장 리스트 수'),
        ),
        migrations.AddField(
            model_name='movie',
            name='category',
            field=models.CharField(max_length=100, blank=True, verbose_name='수집 카테고리'),
        ),
        migrations.AddField(
            model_name='movie',
            name='is_major',
            field=models.BooleanField(default=True, verbose_name='메이저 여부'),
        ),
        migrations.AddField(
            model_name='movie',
            name='watcha_url',
            field=models.URLField(blank=True, verbose_name='왓챠피디아 URL'),
        ),
        migrations.AddField(
            model_name='movie',
            name='collected_at',
            field=models.DateTimeField(null=True, blank=True, verbose_name='수집 일시'),
        ),

        # Meta ordering 업데이트
        migrations.AlterModelOptions(
            name='movie',
            options={
                'verbose_name': '영화',
                'verbose_name_plural': '영화 목록',
                'ordering': ['title_ko'],
            },
        ),
    ]

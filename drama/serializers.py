from rest_framework import serializers
from .models import DramaCategory, Drama, DramaEpisode


class DramaCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DramaCategory
        fields = ['id', 'name', 'slug', 'description']


class DramaEpisodeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = DramaEpisode
        fields = [
            'id', 'episode_no', 'title', 'video_url', 'thumbnail_url',
            'duration_seconds', 'views', 'order', 'uploaded_at'
        ]


class DramaDetailSerializer(serializers.ModelSerializer):
    episodes = DramaEpisodeListSerializer(many=True, read_only=True)
    category = DramaCategorySerializer(read_only=True)
    uploaded_by = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Drama
        fields = [
            'id', 'title', 'slug', 'short_code', 'description',
            'thumbnail_url', 'poster_url', 'category',
            'status', 'uploaded_by', 'created_at', 'views',
            'total_episodes', 'episodes'
        ]


class DramaCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Drama
        fields = [
            'title', 'description', 'category', 'thumbnail_url', 'poster_url'
        ]

    def create(self, validated_data):
        drama = Drama.objects.create(
            user=self.context['request'].user,
            **validated_data
        )
        return drama


class DramaEpisodeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DramaEpisode
        fields = [
            'episode_no', 'title', 'video_url', 'thumbnail_url',
            'duration_seconds', 'description', 'order'
        ]

    def validate(self, data):
        drama = self.context['drama']
        if DramaEpisode.objects.filter(drama=drama, episode_no=data['episode_no']).exists():
            raise serializers.ValidationError({"episode_no": "This episode number already exists for this drama."})
        return data

    def create(self, validated_data):
        drama = self.context['drama']
        episode = DramaEpisode.objects.create(drama=drama, **validated_data)
        # Update total_episodes cache
        drama.total_episodes = drama.episodes.count()
        drama.save(update_fields=['total_episodes'])
        return episode
# drama/views.py
from decimal import Decimal
from datetime import date

from django.db.models import Q, Sum, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import SiteSettings
from core.utils import get_client_ip
from .models import Drama, DramaEpisode, DramaCategory, DramaView, EpisodeView
from .serializers import (
    DramaCategorySerializer,
    DramaCreateUpdateSerializer,
    DramaDetailSerializer,
    DramaEpisodeCreateSerializer,
    DramaEpisodeListSerializer,
)
from .services import calculate_episode_view_earning, update_drama_earnings


# ───────────────────────────────────────────────
# Categories (public)
# ───────────────────────────────────────────────
class DramaCategoryListView(generics.ListAPIView):
    queryset = DramaCategory.objects.filter(is_active=True)
    serializer_class = DramaCategorySerializer
    permission_classes = [AllowAny]


# ───────────────────────────────────────────────
# Creator's own dramas (CRUD) – non-archived by default
# ───────────────────────────────────────────────
class DramaListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Show only non-archived dramas by default
        # If you want to show archived too → add ?show_archived=true query param
        show_archived = request.query_params.get('show_archived', 'false').lower() == 'true'

        qs = Drama.objects.filter(user=request.user)
        if not show_archived:
            qs = qs.filter(is_archived=False)

        dramas = qs.order_by('-created_at')
        serializer = DramaDetailSerializer(dramas, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = DramaCreateUpdateSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            drama = serializer.save()
            return Response(
                DramaDetailSerializer(drama).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DramaDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        # Owner can access even archived items
        return get_object_or_404(Drama, pk=pk, user=self.request.user)

    def get(self, request, pk):
        drama = self.get_object(pk)
        return Response(DramaDetailSerializer(drama).data)

    def patch(self, request, pk):
        drama = self.get_object(pk)
        serializer = DramaCreateUpdateSerializer(
            drama,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(DramaDetailSerializer(drama).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        drama = self.get_object(pk)

        if drama.is_archived:
            return Response(
                {"message": "Drama is already archived"},
                status=status.HTTP_200_OK
            )

        drama.archive()  # soft archive
        return Response(
            {"message": "Drama has been archived successfully"},
            status=status.HTTP_200_OK
        )


# ───────────────────────────────────────────────
# Episodes
# ───────────────────────────────────────────────
class DramaEpisodeCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, drama_pk):
        drama = get_object_or_404(Drama, pk=drama_pk, user=request.user)
        serializer = DramaEpisodeCreateSerializer(
            data=request.data,
            context={'drama': drama}
        )
        if serializer.is_valid():
            episode = serializer.save()
            update_drama_earnings(drama)  # refresh totals
            return Response(
                DramaEpisodeListSerializer(episode).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DramaEpisodeListView(generics.ListAPIView):
    serializer_class = DramaEpisodeListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        drama = get_object_or_404(
            Drama,
            pk=self.kwargs['drama_pk'],
            status='approved',
            is_archived=False
        )
        return drama.episodes.filter(is_active=True).order_by('order', 'episode_no')


# ───────────────────────────────────────────────
# Public browsing – only approved & non-archived
# ───────────────────────────────────────────────
class PublicDramaListView(generics.ListAPIView):
    serializer_class = DramaDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Drama.objects.filter(status='approved', is_archived=False)

        category_slug = self.request.query_params.get('category')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        search_term = self.request.query_params.get('search')
        if search_term:
            qs = qs.filter(
                Q(title__icontains=search_term) |
                Q(description__icontains=search_term)
            )

        return qs.order_by('-approved_at', '-views')


class PublicDramaDetailView(generics.RetrieveAPIView):
    queryset = Drama.objects.filter(status='approved', is_archived=False)
    serializer_class = DramaDetailSerializer
    lookup_field = 'short_code'
    permission_classes = [AllowAny]


# ───────────────────────────────────────────────
# View tracking + earnings
# ───────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def increment_drama_view(request, short_code):
    drama = get_object_or_404(
        Drama,
        short_code=short_code,
        status='approved',
        is_archived=False
    )
    ip = get_client_ip(request)

    today = timezone.now().date()
    already_viewed = DramaView.objects.filter(
        drama=drama,
        ip_address=ip,
        view_date=today
    ).exists()

    if already_viewed:
        return Response({"message": "Already viewed today", "views": drama.views})

    drama.views += 1
    inc_earning = calculate_episode_view_earning(1)
    drama.view_earnings += inc_earning
    drama.earnings += inc_earning
    drama.save(update_fields=['views', 'view_earnings', 'earnings'])

    DramaView.objects.create(drama=drama, ip_address=ip)

    # Optional: credit creator
    # drama.user.pending_earnings += inc_earning
    # drama.user.total_earnings += inc_earning
    # drama.user.save(update_fields=['pending_earnings', 'total_earnings'])

    return Response({
        "message": "View counted",
        "views": drama.views,
        "earning_increment": float(inc_earning)
    })


# ───────────────────────────────────────────────
# EPISODE VIEW COUNT + CREATOR EARNING (FINAL)
# ───────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def increment_episode_view(request, episode_id):
    """
    Episode View + Earning + Drama Total Views + Drama Total Earnings
    """
    try:
        episode = get_object_or_404(
            DramaEpisode,
            id=episode_id,
            is_active=True,
            drama__status='approved',
            drama__is_archived=False
        )

        ip = get_client_ip(request)
        today = timezone.now().date()

        already_viewed = EpisodeView.objects.filter(
            episode=episode,
            ip_address=ip,
            view_date=today
        ).exists()

        if already_viewed:
            return Response({"message": "Already viewed today", "views": episode.views})

        # View Count
        episode.views += 1

        # Earning Calculation (Admin se changeable rate)
        inc_earning = calculate_episode_view_earning(1)

        episode.view_earnings += inc_earning
        episode.earnings += inc_earning
        episode.save(update_fields=['views', 'view_earnings', 'earnings'])

        # Creator Earning
        creator = episode.drama.user
        creator.pending_earnings += inc_earning
        creator.total_earnings += inc_earning
        creator.save(update_fields=['pending_earnings', 'total_earnings'])

        # Log View
        EpisodeView.objects.create(episode=episode, ip_address=ip)

        # Update Drama Totals
        update_drama_earnings(episode.drama)
        episode.drama.update_total_views()   # views bhi update

        return Response({
            "status": "success",
            "message": "View counted",
            "episode_views": episode.views,
            "drama_total_views": episode.drama.views,
            "earning_given": float(inc_earning)
        })

    except Exception as e:
        print(f"Drama Episode View Error: {str(e)}")
        return Response({"error": "Something went wrong"}, status=400)


# ───────────────────────────────────────────────
# Creator earnings summary
# ───────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def creator_drama_earnings_summary(request):
    user = request.user

    # Get all non-archived dramas of the user
    dramas = Drama.objects.filter(user=user, is_archived=False)

    # Aggregate from Drama level (already updated via signals)
    drama_agg = dramas.aggregate(
        total_dramas_views=Sum('views'),
        total_dramas_earnings=Sum('earnings'),
        pending_count=Count('id', filter=Q(status='pending')),
        approved_count=Count('id', filter=Q(status='approved')),
        rejected_count=Count('id', filter=Q(status='rejected')),
    )

    # Get total from ALL episodes (more accurate)
    episodes = DramaEpisode.objects.filter(
        drama__user=user,
        drama__is_archived=False
    )

    episode_agg = episodes.aggregate(
        total_episode_views=Sum('views'),
        total_episode_earnings=Sum('earnings'),
    )

    data = {
        "total_dramas": dramas.count(),
        
        # Views
        "total_views": episode_agg['total_episode_views'] or 0,           # ← Episode se total
        "drama_level_views": drama_agg['total_dramas_views'] or 0,       # backup
        
        # Earnings
        "total_earnings": round(episode_agg['total_episode_earnings'] or Decimal('0.0000'), 4),
        "drama_level_earnings": round(drama_agg['total_dramas_earnings'] or Decimal('0.0000'), 4),
        
        # Status counts
        "pending_dramas": drama_agg['pending_count'] or 0,
        "approved_dramas": drama_agg['approved_count'] or 0,
        "rejected_dramas": drama_agg['rejected_count'] or 0,
    }

    return Response(data)


# ───────────────────────────────────────────────
# Admin – Approval & moderation (exclude archived)
# ───────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_pending_dramas(request):
    pending = Drama.objects.filter(
        status='pending',
        is_archived=False
    ).select_related('user', 'category').order_by('created_at')

    serializer = DramaDetailSerializer(pending, many=True)
    return Response(serializer.data)

# drama/views.py
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_dramas_list(request):
    status_filter = request.query_params.get('status')
    include_archived = request.query_params.get('include_archived', 'false').lower() == 'true'

    qs = Drama.objects.select_related('user', 'category')

    if not include_archived:
        qs = qs.filter(is_archived=False)

    if status_filter and status_filter != 'all':
        qs = qs.filter(status=status_filter)

    qs = qs.order_by('-created_at', '-approved_at')

    serializer = DramaDetailSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_approve_drama(request, pk):
    drama = get_object_or_404(Drama, pk=pk)

    if drama.is_archived:
        return Response(
            {"error": "Cannot approve archived drama"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if drama.status != 'pending':
        return Response(
            {"error": f"Drama is already {drama.status}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    drama.status = 'approved'
    drama.approved_by = request.user
    drama.approved_at = timezone.now()
    drama.rejected_reason = ""
    drama.save(update_fields=['status', 'approved_by', 'approved_at', 'rejected_reason'])

    return Response(DramaDetailSerializer(drama).data)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_delete_drama(request, pk):
    drama = get_object_or_404(Drama, pk=pk)

    if drama.is_archived:
        return Response(
            {"error": "Drama is already archived"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Soft delete using existing archive method
    drama.archive()

    return Response({
        "message": "Drama has been successfully archived",
        "drama": DramaDetailSerializer(drama).data
    })
    
@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_reject_drama(request, pk):
    drama = get_object_or_404(Drama, pk=pk)

    if drama.is_archived:
        return Response(
            {"error": "Cannot reject archived drama"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if drama.status != 'pending':
        return Response(
            {"error": f"Drama is already {drama.status}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    reason = request.data.get('reason', '').strip()[:500]
    drama.status = 'rejected'
    drama.rejected_reason = reason
    drama.save(update_fields=['status', 'rejected_reason'])

    return Response({
        "message": "Drama rejected",
        "drama": DramaDetailSerializer(drama).data
    })
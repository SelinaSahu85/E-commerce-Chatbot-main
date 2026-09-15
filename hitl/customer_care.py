from database.repositories import HitlReviewRepository


def create_review_request(query: str):
    return HitlReviewRepository.create_review(query)


def resolve_review(review_id: str, human_response: str):
    HitlReviewRepository.resolve(review_id, human_response)


def pending_reviews():
    return HitlReviewRepository.pending()

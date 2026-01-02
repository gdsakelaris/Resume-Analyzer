"""
Evaluation model for storing AI-generated candidate assessments.

This table stores the results of Starscreen's AI scoring engine,
including relevance indicators, category breakdowns, and narrative explanations.

NOTE: Relevance indicators are decision-support guidance, not hiring decisions.
"""

from sqlalchemy import Column, Integer, ForeignKey, Float, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class Evaluation(Base):
    """
    AI-generated evaluation of a candidate against a job posting.

    The Starscreen Intelligence Layer produces:
    - match_score: Overall fit (0-100)
    - category_scores: Breakdown by skill/requirement
    - summary: Executive summary of candidate fit
    - pros/cons: Structured strengths and weaknesses
    """
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)

    # Multi-tenancy: Inherited from candidate, denormalized for query performance
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("users.tenant_id"), nullable=False, index=True)

    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # The Headline Score (0-100)
    match_score = Column(Float, nullable=False, index=True)

    # The "Why" - A structured JSON breakdown
    # Example: {"Cloud Skills": 85, "Python": 90, "Leadership": 40}
    category_scores = Column(JSONB, nullable=False)

    # The Narrative - AI explaining the decision
    summary = Column(Text, nullable=False)  # Executive summary
    pros = Column(JSONB, nullable=True)     # List of strengths
    cons = Column(JSONB, nullable=True)     # List of gaps/weaknesses

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    candidate = relationship("Candidate", back_populates="evaluation")

    def __repr__(self):
        return f"<Evaluation(candidate_id={self.candidate_id}, match_score={self.match_score})>"

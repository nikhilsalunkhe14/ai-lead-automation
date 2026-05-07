"""
AI Lead Scoring Service - Professional lead scoring with AI
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
from src.utils.ai_service import AIService

class ScoringService:
    """Professional lead scoring service with AI integration"""
    
    def __init__(self):
        self.ai_service = AIService()
        self.scoring_factors = {
            'message_quality': {'weight': 0.25, 'max_score': 25},
            'contact_completeness': {'weight': 0.20, 'max_score': 20},
            'urgency_indicators': {'weight': 0.20, 'max_score': 20},
            'professional_indicators': {'weight': 0.15, 'max_score': 15},
            'budget_potential': {'weight': 0.20, 'max_score': 20}
        }
    
    def score_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Score a lead using AI and rule-based scoring"""
        try:
            # Get AI-based score
            ai_score = self.ai_service.score_lead(lead_data)
            
            # Get rule-based score
            rule_score = self._calculate_rule_based_score(lead_data)
            
            # Combine scores (70% AI, 30% rules)
            final_score = (ai_score['score'] * 0.7) + (rule_score['score'] * 0.3)
            
            # Determine confidence
            confidence = min(ai_score['confidence'], rule_score['confidence'])
            
            # Generate recommendations
            recommendations = self._generate_recommendations(final_score, lead_data)
            
            # Categorize lead
            category = self._categorize_lead(final_score)
            
            return {
                'success': True,
                'score': round(final_score, 1),
                'confidence': round(confidence, 1),
                'category': category,
                'ai_score': ai_score,
                'rule_score': rule_score,
                'factors': self._get_scoring_factors(final_score, lead_data),
                'recommendations': recommendations,
                'next_actions': self._get_next_actions(final_score, category),
                'estimated_value': self._estimate_value(final_score, lead_data),
                'urgency_level': self._determine_urgency(final_score, lead_data),
                'scored_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error scoring lead: {e}")
            return {
                'success': False,
                'message': 'Failed to score lead',
                'error': str(e)
            }
    
    def score_multiple_leads(self, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Score multiple leads for batch processing"""
        try:
            results = []
            
            for lead in leads:
                score_result = self.score_lead(lead)
                results.append({
                    'lead_id': lead.get('id'),
                    'score': score_result
                })
            
            # Calculate batch statistics
            scores = [r['score']['score'] for r in results if r['score'].get('success')]
            avg_score = sum(scores) / len(scores) if scores else 0
            
            return {
                'success': True,
                'results': results,
                'batch_stats': {
                    'total_leads': len(leads),
                    'successful_scores': len(scores),
                    'average_score': round(avg_score, 1),
                    'high_value_leads': len([s for s in scores if s >= 70]),
                    'medium_value_leads': len([s for s in scores if 40 <= s < 70]),
                    'low_value_leads': len([s for s in scores if s < 40])
                }
            }
            
        except Exception as e:
            logging.error(f"Error scoring multiple leads: {e}")
            return {
                'success': False,
                'message': 'Failed to score leads',
                'error': str(e)
            }
    
    def get_scoring_insights(self, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get insights from lead scoring"""
        try:
            # Score all leads
            scoring_results = self.score_multiple_leads(leads)
            
            if not scoring_results['success']:
                return scoring_results
            
            results = scoring_results['results']
            scores = [r['score']['score'] for r in results if r['score'].get('success')]
            
            # Analyze patterns
            insights = {
                'score_distribution': self._analyze_score_distribution(scores),
                'common_factors': self._analyze_common_factors(results),
                'improvement_areas': self._analyze_improvement_areas(results),
                'trending_patterns': self._analyze_trends(results),
                'recommendations': self._generate_system_recommendations(scores)
            }
            
            return {
                'success': True,
                'insights': insights,
                'batch_stats': scoring_results['batch_stats']
            }
            
        except Exception as e:
            logging.error(f"Error getting scoring insights: {e}")
            return {
                'success': False,
                'message': 'Failed to analyze scoring insights',
                'error': str(e)
            }
    
    def _calculate_rule_based_score(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate rule-based score"""
        score = 0
        factors = []
        
        # Message quality scoring
        message = lead_data.get('message', '')
        message_score = 0
        
        if len(message) > 200:
            message_score += 10
            factors.append('Very detailed message')
        elif len(message) > 100:
            message_score += 7
            factors.append('Detailed message')
        elif len(message) > 50:
            message_score += 4
            factors.append('Moderate detail')
        
        # Professional language indicators
        professional_words = ['partnership', 'collaboration', 'opportunity', 'proposal', 'investment', 'budget', 'timeline']
        if any(word in message.lower() for word in professional_words):
            message_score += 8
            factors.append('Professional language used')
        
        score += message_score * self.scoring_factors['message_quality']['weight']
        
        # Contact completeness scoring
        contact_score = 0
        if lead_data.get('phone'):
            contact_score += 10
            factors.append('Phone provided')
        
        if lead_data.get('company'):
            contact_score += 10
            factors.append('Company provided')
        
        if lead_data.get('website'):
            contact_score += 5
            factors.append('Website provided')
        
        score += contact_score * self.scoring_factors['contact_completeness']['weight']
        
        # Urgency indicators
        urgency_score = 0
        urgent_words = ['urgent', 'asap', 'immediately', 'need', 'quickly', 'soon', 'deadline']
        message_lower = message.lower()
        
        urgency_count = sum(1 for word in urgent_words if word in message_lower)
        if urgency_count >= 3:
            urgency_score += 15
            factors.append('High urgency indicated')
        elif urgency_count >= 2:
            urgency_score += 10
            factors.append('Moderate urgency indicated')
        elif urgency_count >= 1:
            urgency_score += 5
            factors.append('Some urgency indicated')
        
        score += urgency_score * self.scoring_factors['urgency_indicators']['weight']
        
        # Professional indicators
        professional_score = 0
        email = lead_data.get('email', '').lower()
        
        # Professional email domains
        professional_domains = ['gmail.com', 'yahoo.com', 'hotmail.com']
        if not any(domain in email for domain in professional_domains):
            professional_score += 5
            factors.append('Professional email domain')
        
        # Company email
        if lead_data.get('company') and lead_data.get('company').lower() in email:
            professional_score += 8
            factors.append('Company email address')
        
        score += professional_score * self.scoring_factors['professional_indicators']['weight']
        
        # Budget potential
        budget_score = 0
        budget_words = ['budget', 'price', 'cost', 'investment', '$', 'k', 'm']
        budget_indicators = sum(1 for word in budget_words if word in message_lower)
        
        if budget_indicators >= 2:
            budget_score += 15
            factors.append('Budget discussion present')
        elif budget_indicators >= 1:
            budget_score += 8
            factors.append('Financial terms mentioned')
        
        score += budget_score * self.scoring_factors['budget_potential']['weight']
        
        return {
            'success': True,
            'score': min(100, score),
            'confidence': 85,
            'factors': factors
        }
    
    def _generate_recommendations(self, score: float, lead_data: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on score"""
        recommendations = []
        
        if score >= 80:
            recommendations.append('Immediate follow-up required - High value lead')
            recommendations.append('Consider priority scheduling for meeting')
        elif score >= 60:
            recommendations.append('Follow up within 24 hours')
            recommendations.append('Prepare detailed proposal')
        elif score >= 40:
            recommendations.append('Standard follow-up process')
            recommendations.append('Qualify for budget and timeline')
        else:
            recommendations.append('Nurture campaign recommended')
            recommendations.append('Add to long-term follow-up sequence')
        
        # Specific recommendations based on data
        if not lead_data.get('phone'):
            recommendations.append('Request phone number for better contact')
        
        if not lead_data.get('company'):
            recommendations.append('Research company background')
        
        return recommendations
    
    def _categorize_lead(self, score: float) -> str:
        """Categorize lead based on score"""
        if score >= 80:
            return 'Hot'
        elif score >= 60:
            return 'Warm'
        elif score >= 40:
            return 'Cool'
        else:
            return 'Cold'
    
    def _get_scoring_factors(self, score: float, lead_data: Dict[str, Any]) -> List[str]:
        """Get detailed scoring factors"""
        factors = []
        
        # Message quality
        message_len = len(lead_data.get('message', ''))
        if message_len > 200:
            factors.append(f'Excellent message detail (+15 points)')
        elif message_len > 100:
            factors.append(f'Good message detail (+10 points)')
        
        # Contact info
        if lead_data.get('phone'):
            factors.append('Phone number provided (+10 points)')
        
        if lead_data.get('company'):
            factors.append('Company information provided (+10 points)')
        
        # Urgency
        urgent_words = ['urgent', 'asap', 'immediately']
        message_lower = lead_data.get('message', '').lower()
        if any(word in message_lower for word in urgent_words):
            factors.append('Urgency indicators detected (+10 points)')
        
        return factors
    
    def _get_next_actions(self, score: float, category: str) -> List[str]:
        """Get recommended next actions"""
        actions = []
        
        if category == 'Hot':
            actions.extend([
                'Schedule immediate call',
                'Prepare personalized proposal',
                'Assign to senior sales rep',
                'Set up follow-up reminders'
            ])
        elif category == 'Warm':
            actions.extend([
                'Send personalized email',
                'Schedule discovery call',
                'Research company needs',
                'Prepare qualification questions'
            ])
        elif category == 'Cool':
            actions.extend([
                'Add to nurture sequence',
                'Send educational content',
                'Schedule follow-up for next week',
                'Monitor engagement'
            ])
        else:  # Cold
            actions.extend([
                'Add to long-term nurture',
                'Send general information',
                'Monitor for engagement',
                'Periodic check-ins'
            ])
        
        return actions
    
    def _estimate_value(self, score: float, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate potential value of lead"""
        base_value = 0
        
        if score >= 80:
            base_value = 50000
        elif score >= 60:
            base_value = 25000
        elif score >= 40:
            base_value = 10000
        else:
            base_value = 5000
        
        # Adjust based on company presence
        if lead_data.get('company'):
            base_value *= 1.5
        
        # Adjust based on professional indicators
        message = lead_data.get('message', '').lower()
        if any(word in message for word in ['budget', 'investment', 'partnership']):
            base_value *= 1.3
        
        return {
            'estimated_value': round(base_value, 2),
            'confidence': 'high' if score >= 60 else 'medium' if score >= 40 else 'low',
            'currency': 'USD'
        }
    
    def _determine_urgency(self, score: float, lead_data: Dict[str, Any]) -> str:
        """Determine urgency level"""
        message = lead_data.get('message', '').lower()
        urgent_words = ['urgent', 'asap', 'immediately', 'need', 'quickly']
        
        urgency_count = sum(1 for word in urgent_words if word in message)
        
        if urgency_count >= 2 or score >= 70:
            return 'High'
        elif urgency_count >= 1 or score >= 50:
            return 'Medium'
        else:
            return 'Low'
    
    def _analyze_score_distribution(self, scores: List[float]) -> Dict[str, Any]:
        """Analyze score distribution"""
        if not scores:
            return {}
        
        scores.sort()
        total = len(scores)
        
        return {
            'mean': sum(scores) / total,
            'median': scores[total // 2],
            'min': min(scores),
            'max': max(scores),
            'std_dev': self._calculate_std_dev(scores),
            'quartiles': {
                'q1': scores[total // 4],
                'q2': scores[total // 2],
                'q3': scores[3 * total // 4]
            }
        }
    
    def _analyze_common_factors(self, results: List[Dict[str, Any]]) -> List[str]:
        """Analyze common scoring factors"""
        factor_counts = {}
        
        for result in results:
            if result['score'].get('success') and result['score'].get('factors'):
                for factor in result['score']['factors']:
                    factor_counts[factor] = factor_counts.get(factor, 0) + 1
        
        # Get top factors
        sorted_factors = sorted(factor_counts.items(), key=lambda x: x[1], reverse=True)
        return [factor[0] for factor in sorted_factors[:5]]
    
    def _analyze_improvement_areas(self, results: List[Dict[str, Any]]) -> List[str]:
        """Analyze areas for improvement"""
        low_score_factors = []
        
        for result in results:
            if result['score'].get('success') and result['score'].get('score', 0) < 40:
                if result['score'].get('factors'):
                    low_score_factors.extend(result['score']['factors'])
        
        # Count common issues
        issue_counts = {}
        for factor in low_score_factors:
            if 'missing' in factor.lower() or 'not provided' in factor.lower():
                issue_counts['Incomplete Information'] = issue_counts.get('Incomplete Information', 0) + 1
            elif 'low' in factor.lower():
                issue_counts['Low Engagement'] = issue_counts.get('Low Engagement', 0) + 1
        
        return list(issue_counts.keys())
    
    def _analyze_trends(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze scoring trends"""
        # This would analyze trends over time
        # For now, return basic statistics
        scores = [r['score']['score'] for r in results if r['score'].get('success')]
        
        return {
            'average_score': sum(scores) / len(scores) if scores else 0,
            'high_value_percentage': len([s for s in scores if s >= 70]) / len(scores) * 100 if scores else 0,
            'trend_direction': 'stable'  # Would calculate from historical data
        }
    
    def _generate_system_recommendations(self, scores: List[float]) -> List[str]:
        """Generate system-level recommendations"""
        recommendations = []
        
        if not scores:
            return recommendations
        
        avg_score = sum(scores) / len(scores)
        
        if avg_score < 40:
            recommendations.append('Consider improving lead qualification process')
            recommendations.append('Review lead sources for quality')
        elif avg_score < 60:
            recommendations.append('Implement lead nurturing campaigns')
            recommendations.append('Provide better qualification training')
        
        high_value_percentage = len([s for s in scores if s >= 70]) / len(scores) * 100
        if high_value_percentage < 20:
            recommendations.append('Focus on higher-value lead sources')
        
        return recommendations
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

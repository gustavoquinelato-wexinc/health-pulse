-- ML Training Data Readiness Check
-- Run this to assess what models you can train per tenant

-- 1. Story Point Prediction Readiness
SELECT 
    tenant_id,
    COUNT(*) as total_work_items,
    COUNT(CASE WHEN story_points IS NOT NULL AND story_points > 0 THEN 1 END) as items_with_story_points,
    ROUND(
        COUNT(CASE WHEN story_points IS NOT NULL AND story_points > 0 THEN 1 END) * 100.0 / COUNT(*), 
        2
    ) as story_point_coverage_pct,
    MIN(created) as oldest_item,
    MAX(created) as newest_item
FROM work_items 
WHERE active = true
GROUP BY tenant_id
ORDER BY items_with_story_points DESC;

-- 2. Lead Time Prediction Readiness  
SELECT 
    tenant_id,
    COUNT(*) as total_work_items,
    COUNT(CASE WHEN total_lead_time_seconds IS NOT NULL AND total_lead_time_seconds > 0 THEN 1 END) as items_with_lead_time,
    COUNT(CASE WHEN work_first_completed_at IS NOT NULL THEN 1 END) as completed_items,
    ROUND(AVG(total_lead_time_seconds) / 86400.0, 2) as avg_lead_time_days,
    ROUND(STDDEV(total_lead_time_seconds) / 86400.0, 2) as stddev_lead_time_days
FROM work_items 
WHERE active = true
GROUP BY tenant_id
ORDER BY items_with_lead_time DESC;

-- 3. Rework Risk Prediction Readiness
SELECT 
    tenant_id,
    COUNT(*) as total_prs,
    COUNT(CASE WHEN status = 'merged' THEN 1 END) as merged_prs,
    COUNT(CASE WHEN rework_commit_count > 2 THEN 1 END) as high_rework_prs,
    ROUND(
        COUNT(CASE WHEN rework_commit_count > 2 THEN 1 END) * 100.0 / 
        COUNT(CASE WHEN status = 'merged' THEN 1 END), 
        2
    ) as rework_rate_pct,
    ROUND(AVG(rework_commit_count), 2) as avg_rework_commits
FROM prs 
WHERE active = true
GROUP BY tenant_id
ORDER BY merged_prs DESC;

-- 4. Feature Quality Assessment
SELECT 
    tenant_id,
    -- Text content quality
    COUNT(CASE WHEN LENGTH(summary) > 10 THEN 1 END) as items_with_good_summary,
    COUNT(CASE WHEN LENGTH(description) > 50 THEN 1 END) as items_with_good_description,
    
    -- Team assignment quality
    COUNT(CASE WHEN assignee IS NOT NULL THEN 1 END) as items_with_assignee,
    COUNT(CASE WHEN team IS NOT NULL THEN 1 END) as items_with_team,
    
    -- Workflow data quality
    COUNT(CASE WHEN workflow_complexity_score > 0 THEN 1 END) as items_with_workflow_data,
    
    COUNT(*) as total_items
FROM work_items 
WHERE active = true
GROUP BY tenant_id;

-- 5. Training Data Recommendations
WITH tenant_readiness AS (
    SELECT 
        tenant_id,
        COUNT(CASE WHEN story_points IS NOT NULL AND story_points > 0 THEN 1 END) as story_point_samples,
        COUNT(CASE WHEN total_lead_time_seconds IS NOT NULL AND work_first_completed_at IS NOT NULL THEN 1 END) as lead_time_samples,
        COUNT(*) as total_samples
    FROM work_items 
    WHERE active = true 
      AND created > NOW() - INTERVAL '2 years'  -- Recent data only
    GROUP BY tenant_id
)
SELECT 
    tenant_id,
    story_point_samples,
    lead_time_samples,
    total_samples,
    CASE 
        WHEN story_point_samples >= 200 THEN 'READY'
        WHEN story_point_samples >= 100 THEN 'MARGINAL' 
        ELSE 'NOT_READY'
    END as story_point_model_readiness,
    CASE 
        WHEN lead_time_samples >= 150 THEN 'READY'
        WHEN lead_time_samples >= 75 THEN 'MARGINAL'
        ELSE 'NOT_READY' 
    END as lead_time_model_readiness
FROM tenant_readiness
ORDER BY story_point_samples DESC;

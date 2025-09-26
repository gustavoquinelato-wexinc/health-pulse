-- Story Point Prediction Model Training
-- Train per tenant for data isolation

-- Step 1: Create training view with features
CREATE OR REPLACE VIEW story_point_training_data AS
WITH team_stats AS (
    -- Calculate team historical performance
    SELECT 
        tenant_id,
        team,
        COUNT(*) as team_total_items,
        AVG(story_points) as team_avg_story_points,
        STDDEV(story_points) as team_stddev_story_points,
        AVG(total_lead_time_seconds / 86400.0) as team_avg_lead_time_days
    FROM work_items 
    WHERE story_points IS NOT NULL 
      AND story_points > 0
      AND active = true
    GROUP BY tenant_id, team
),
assignee_stats AS (
    -- Calculate assignee historical performance  
    SELECT 
        tenant_id,
        assignee,
        COUNT(*) as assignee_total_items,
        AVG(story_points) as assignee_avg_story_points,
        AVG(total_lead_time_seconds / 86400.0) as assignee_avg_lead_time_days
    FROM work_items 
    WHERE story_points IS NOT NULL 
      AND story_points > 0
      AND assignee IS NOT NULL
      AND active = true
    GROUP BY tenant_id, assignee
)
SELECT 
    wi.tenant_id,
    wi.id as work_item_id,
    wi.key as work_item_key,
    
    -- Target variable
    wi.story_points as target_story_points,
    
    -- Text features
    LENGTH(COALESCE(wi.summary, '')) as summary_length,
    LENGTH(COALESCE(wi.description, '')) as description_length,
    LENGTH(COALESCE(wi.acceptance_criteria, '')) as acceptance_criteria_length,
    
    -- Categorical features (one-hot encoded)
    CASE WHEN wi.priority = 'Highest' THEN 1 ELSE 0 END as is_highest_priority,
    CASE WHEN wi.priority = 'High' THEN 1 ELSE 0 END as is_high_priority,
    CASE WHEN wi.priority = 'Medium' THEN 1 ELSE 0 END as is_medium_priority,
    CASE WHEN wi.assignee IS NOT NULL THEN 1 ELSE 0 END as has_assignee,
    CASE WHEN wi.team IS NOT NULL THEN 1 ELSE 0 END as has_team,
    
    -- Workflow complexity features
    COALESCE(wi.workflow_complexity_score, 0) as workflow_complexity_score,
    COALESCE(wi.total_work_starts, 0) as total_work_starts,
    CASE WHEN wi.rework_indicator = true THEN 1 ELSE 0 END as has_rework_indicator,
    
    -- Historical team performance features
    COALESCE(ts.team_avg_story_points, 3.0) as team_avg_story_points,
    COALESCE(ts.team_total_items, 0) as team_experience,
    
    -- Historical assignee performance features  
    COALESCE(as_stats.assignee_avg_story_points, 3.0) as assignee_avg_story_points,
    COALESCE(as_stats.assignee_total_items, 0) as assignee_experience,
    
    -- Time features
    EXTRACT(MONTH FROM wi.created) as created_month,
    EXTRACT(DOW FROM wi.created) as created_day_of_week,
    
    -- Custom field indicators (check if they contain data)
    CASE WHEN wi.custom_field_01 IS NOT NULL THEN 1 ELSE 0 END as has_custom_field_01,
    CASE WHEN wi.custom_field_02 IS NOT NULL THEN 1 ELSE 0 END as has_custom_field_02,
    CASE WHEN wi.custom_field_03 IS NOT NULL THEN 1 ELSE 0 END as has_custom_field_03

FROM work_items wi
LEFT JOIN team_stats ts ON wi.tenant_id = ts.tenant_id AND wi.team = ts.team
LEFT JOIN assignee_stats as_stats ON wi.tenant_id = as_stats.tenant_id AND wi.assignee = as_stats.assignee
WHERE wi.story_points IS NOT NULL 
  AND wi.story_points > 0 
  AND wi.story_points <= 21  -- Remove outliers
  AND wi.active = true
  AND wi.created > NOW() - INTERVAL '2 years';  -- Recent data only

-- Step 2: Train model for specific tenant (example for tenant_id = 1)
-- This needs to be executed per tenant
SELECT pgml.train(
    project_name => 'story_point_predictor_tenant_1_v1',
    task => 'regression',
    relation_name => 'story_point_training_data',
    y_column_name => 'target_story_points',
    algorithm => 'xgboost',
    hyperparams => '{
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8
    }',
    test_size => 0.2,
    test_sampling => 'random'
) WHERE tenant_id = 1;

-- Step 3: Evaluate model performance
SELECT * FROM pgml.models 
WHERE project_name = 'story_point_predictor_tenant_1_v1'
ORDER BY created_at DESC 
LIMIT 1;

-- Step 4: Test prediction
SELECT 
    work_item_key,
    target_story_points as actual_story_points,
    pgml.predict(
        'story_point_predictor_tenant_1_v1',
        ARRAY[
            summary_length::float,
            description_length::float,
            acceptance_criteria_length::float,
            is_highest_priority::float,
            is_high_priority::float,
            is_medium_priority::float,
            has_assignee::float,
            has_team::float,
            workflow_complexity_score::float,
            total_work_starts::float,
            has_rework_indicator::float,
            team_avg_story_points::float,
            team_experience::float,
            assignee_avg_story_points::float,
            assignee_experience::float,
            created_month::float,
            created_day_of_week::float,
            has_custom_field_01::float,
            has_custom_field_02::float,
            has_custom_field_03::float
        ]
    ) as predicted_story_points
FROM story_point_training_data 
WHERE tenant_id = 1
LIMIT 10;

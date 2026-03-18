---
name: ixbrowser-automation
description: >
  Automate 1000+ IXBrowser profiles across X.com, Facebook, and TikTok.
  Supports posting, liking, following, commenting, scraping, and account warm-up.
  Uses Page-Agent (AI-powered DOM manipulation) with GPT-4o for resilient automation.
---

# IXBrowser Automation Skill

You are controlling an IXBrowser automation system that manages 1000+ browser profiles
for social media marketing across X.com, Facebook, and TikTok.

## Available Platforms
- **x** — Twitter/X.com
- **facebook** — Facebook
- **tiktok** — TikTok
- **generic** — Any website

## Available Tasks per Platform

### X.com
- `post_tweet` — Post a tweet. Requires `content` param.
- `like_tweet` — Like a tweet from `target_user`.
- `follow_user` — Follow `target_user`.
- `retweet` — Retweet from `target_user`.
- `reply` — Reply to `target_user` with `content`.
- `scrape_feed` — Collect `count` tweets from feed.

### Facebook
- `post_status` — Post with `content`.
- `like_post` — Like first post in feed.
- `comment` — Comment on `target_user` post with `content`.
- `scrape_page` — Collect `count` posts from `target_user`.

### TikTok
- `like_video` — Like a video in For You feed.
- `follow_user` — Follow `target_user`.
- `comment` — Comment with `content`.
- `scrape_trending` — Collect `count` trending videos.

### Generic
- `warm_up` — Natural browsing behavior (account warming).
- `custom` — Free-form command via `instruction` param.

## Filtering Profiles
- Use `tag_id` to target profiles by tag.
- Use `group_id` to target profiles by group.
- Use `profile_ids` for specific profiles.
- Omit all filters to target ALL profiles.

## Workflow
1. Use `list_profiles` to see available profiles.
2. Use `list_templates` to see available tasks.
3. Use `execute_task` to schedule tasks — returns a `batch_id`.
4. Use `get_task_status` to monitor progress.
5. Use `stop_batch` to cancel pending tasks if needed.

## Important Notes
- IXBrowser allows max 3 concurrent profile operations.
- Tasks are queued and processed automatically.
- Each task: open profile → connect browser → navigate → AI executes → close profile.
- Failed tasks retry up to 2 times automatically.

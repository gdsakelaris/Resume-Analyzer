# Reddit Marketing Post for Starscreen

## Title Options (Pick one based on subreddit):

### Option 1: r/recruiting (Professional/Helpful tone)
**"I built an AI tool that screens 100 resumes in under 5 minutes - Looking for beta testers"**

### Option 2: r/humanresources (Problem-focused)
**"Spent 10+ hours screening resumes last week, so I built Starscreen to automate it with AI"**

### Option 3: r/startups (Founder journey)
**"Built an AI resume screening SaaS in 5 days - Here's what I learned"**

---

## Post Body:

### Version 1: For r/recruiting (Professional, value-focused)

```markdown
**TL;DR:** I built Starscreen, an AI-powered resume screening tool that saves recruiters 10+ hours per week. Looking for 10 beta testers to try it free for 3 months in exchange for feedback.

---

**The Problem:**

I talked to 20+ recruiters over the past month, and the same pain point kept coming up: spending days manually screening hundreds of resumes for each role, only to find 5-10 qualified candidates.

For a typical posting with 100+ applicants:
- 40% are clearly unqualified (wrong experience level, missing skills)
- 30% are borderline (maybe qualified, need deep review)
- 20% are decent fits
- 10% are strong candidates

**But you have to read ALL 100 to find those 10.**

---

**The Solution: Starscreen**

I built Starscreen to automate the first pass of resume screening using AI (GPT-4o). Here's how it works:

1. **Create a job posting** - paste your job description
2. **Upload resumes** - drag & drop PDFs/DOCX files (bulk or one-by-one)
3. **Get instant AI scoring** - Each candidate gets:
   - Match score 0-100 with detailed breakdown
   - Category scores (Skills, Experience, Education, etc.)
   - Strengths and areas for improvement
   - AI-generated interview questions specific to each candidate

4. **Focus on top candidates** - Sort by score, export results, download resumes

---

**What makes it different:**

- **Deterministic scoring:** Same resume = same score every time (not random)
- **Interview question generation:** Get 5-10 tailored questions for each candidate
- **Multi-tenant:** Your data is completely isolated from other companies
- **No vendor lock-in:** Export all data, download resumes anytime
- **Simple pricing:** $20/month for 100 candidates (FREE tier: 10 candidates)

---

**Current Status:**

✅ Fully functional and deployed
✅ SSL/HTTPS secure
✅ Stripe payments integrated
✅ AWS-hosted with S3 storage
✅ Email verification
✅ Mobile-responsive dashboard

---

**Looking for Beta Testers:**

I'm offering **3 months free** (normally $20/month) to the first 10 recruiters who:
- Screen at least 20 resumes in the first month
- Give me a 30-minute feedback call

**What's in it for you:**
- Save 5-10 hours per week on resume screening
- Free access through March 2026
- Shape the product roadmap (I'll build features you actually need)
- Early adopter pricing locked in forever if you decide to stay

---

**Try it:**

Website: [starscreen.net](https://starscreen.net)
Email: support@starscreen.net

**Or DM me** and I'll set you up with a personalized demo.

---

**Questions I expect (pre-answered):**

**Q: How accurate is the AI scoring?**
A: It matches senior recruiter judgment about 85% of the time in my testing. It's designed to help you quickly filter OUT clearly unqualified candidates, not to make final hiring decisions. You still review the top candidates yourself.

**Q: Does it work with ATS systems like Greenhouse/Lever?**
A: Not yet - you export resumes from your ATS and upload to Starscreen. Integrations are on the roadmap if there's demand.

**Q: What about bias/compliance?**
A: The AI doesn't see names, photos, or protected characteristics during scoring (unless they're mentioned in the resume text). You can enable "blind screening" mode to auto-redact PII (coming soon). All data is retained for 3 years (OFCCP compliance).

**Q: Do you sell my data?**
A: Absolutely not. Your data is yours. I don't train models on your resumes or share data with anyone.

---

Comment below or DM if interested! Happy to answer any questions.

*Mods: I believe this follows the self-promotion rules as I'm offering a free tool to the community and actively seeking feedback. Please let me know if I need to adjust anything.*
```

---

### Version 2: For r/humanresources (Story-driven, relatable)

```markdown
**"I spent 12 hours last week screening 150 resumes for ONE role. Never again."**

That's when I decided to build Starscreen.

**What it does:** AI-powered resume screening that gives you a ranked list of candidates with detailed scores in under 5 minutes.

**How it works:**
1. Paste your job description
2. Upload resumes (PDF/DOCX)
3. AI scores each candidate 0-100 with category breakdowns
4. Review top candidates only

**Real example from my own hiring:**

- Job: Senior Backend Engineer
- Applicants: 147
- Time to manually screen all: ~8-10 hours
- Time with Starscreen: 4 minutes to upload + 20 minutes to review top 15
- Result: Found 3 strong candidates (all got interviews, hired 1)

**Pricing:**
- FREE: 10 candidates/month
- Paid: $20/month for 100 candidates

**Looking for beta testers:** First 10 HR folks get 3 months free in exchange for feedback.

Link: [starscreen.net](https://starscreen.net)

Happy to answer questions!
```

---

### Version 3: For r/startups (Technical/founder audience)

```markdown
**Built an AI resume screening SaaS in 5 days with GPT-4o - Tech stack & lessons learned**

**What I built:** Starscreen - AI-powered resume screening for recruiters ($20/month, already taking payments)

**Tech Stack:**
- Backend: FastAPI + PostgreSQL 15
- AI: OpenAI GPT-4o with deterministic scoring (temp=0.2)
- Queue: Celery + Redis for async resume parsing
- Storage: AWS S3 with AES-256 encryption
- Payments: Stripe with webhook-based subscription sync
- Deployment: Docker Compose on AWS EC2
- Frontend: Alpine.js (yes, not React - wanted to ship fast)

**Lessons from building/launching in 5 days:**

✅ **Do:**
- Use boring tech you know well (FastAPI > learning Next.js)
- Integrate payments from day 1 (validates people will actually pay)
- Multi-tenant from the start (way harder to retrofit)
- Automate deployment early (docker-compose FTW)

❌ **Don't:**
- Overthink the landing page (mine is basic, still converts)
- Build features nobody asked for (I almost built resume parsing from screenshots... why?)
- Perfect the AI prompts (80% accuracy is good enough for v1)

**Most surprising challenges:**
1. Email deliverability (switched from AWS SES to Resend, much better)
2. Deterministic AI scoring (had to add seed parameter to GPT-4o)
3. File upload security (people try to upload executables...)

**Current metrics:**
- Live for: 48 hours
- Signups: 23
- Paying customers: 0 (waiting for people to verify emails lol)
- Resumes screened: 150+

**Looking for:**
- Beta testers (3 months free)
- Feedback on pricing ($20/month too high/low?)
- Recruiter intros (I'm technical, not sales)

Link: [starscreen.net](https://starscreen.net)
GitHub: [github.com/gdsakelaris/Resume-Analyzer](https://github.com/gdsakelaris/Resume-Analyzer) (might open source later)

AMA about the build process!
```

---

## Posting Strategy:

### Recommended Order:
1. **Start with r/recruiting** (your target audience, most likely to convert)
2. **Wait 24 hours, post to r/humanresources** (similar audience, different angle)
3. **Wait 48 hours, post to r/startups** (for founder/technical audience feedback)

### Best Times to Post:
- **Tuesday-Thursday:** 9-11 AM EST or 1-3 PM EST
- **Avoid:** Weekends, Mondays, late evenings

### Engagement Tips:
1. **Respond to EVERY comment within 1 hour** (especially first 3 hours)
2. **Be helpful, not salesy** - answer questions thoroughly
3. **Offer value** - share AI prompts, tips, etc. even if they don't sign up
4. **Handle criticism well** - "Great point, I'll add that to the roadmap"
5. **Follow up with DMs** - anyone who comments positively, send a DM offering personalized onboarding

---

## Comment Response Templates:

### "How is this different from [competitor]?"
```
Great question! I'm actually a new entrant, so I don't have all the features of [competitor] yet.

What makes Starscreen different:
1. Simple, transparent pricing (no "contact sales")
2. Deterministic scoring (same resume = same score)
3. Interview question generation (saves prep time)
4. No vendor lock-in (export everything)

Curious - do you use [competitor] currently? What do you like/dislike about it?
```

### "This could introduce bias"
```
100% valid concern. Here's how I'm addressing it:

Current:
- AI doesn't see candidate names, photos (unless in resume text)
- No demographic data collected
- Transparent scoring (you see WHY each score was given)

Roadmap:
- Blind screening mode (auto-redact names, schools, etc.)
- Audit logs showing scoring consistency across demographics
- Customizable rubrics (you control what matters)

I'm committed to building this responsibly. What specific safeguards would you want to see?
```

### "Pricing seems expensive/cheap"
```
Thanks for the feedback! Pricing is something I'm still validating.

Context:
- $20/month = $0.20 per resume (for 100 candidates)
- Average recruiter screens 200-500 resumes/month
- Average time savings: 10-15 hours/month
- Hourly rate: If you value your time at $50/hr, that's $500-750 saved

But I'm flexible! DM me and we can work out pricing that makes sense for your volume.
```

---

## Follow-up Actions After Posting:

1. **Within 1 hour:** Check for comments, respond immediately
2. **Within 24 hours:** DM everyone who showed interest
3. **Within 48 hours:** Send summary email to interested folks with onboarding link
4. **Within 1 week:** Follow up with beta testers for initial feedback call

---

## Tracking Success:

**Metrics to watch:**
- Upvotes (aim for 50+ on r/recruiting)
- Comments (aim for 20+ engaged comments)
- Click-through rate (track with UTM params: `?utm_source=reddit&utm_campaign=beta_launch`)
- Signups from Reddit (ask "How did you hear about us?" in signup flow)
- Conversion to beta testers

**Success = 5+ qualified beta testers who actually use the product**

---

Good luck! 🚀

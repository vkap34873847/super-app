package com.theplaybook.app.data.local

import com.theplaybook.app.data.local.entity.CourseEntity
import com.theplaybook.app.data.local.entity.LessonEntity
import com.theplaybook.app.data.local.entity.ModuleEntity

object SeedData {

    fun getCourses() = listOf(
        CourseEntity(
            id = 1,
            title = "The Dating Playbook",
            description = "Master the art of dating, attraction, and relationships. Real strategies that actually work in the field.",
            subtitle = "Become the prize",
            iconRes = 0,
            moduleCount = 4,
            lessonCount = 16,
            estimatedMinutes = 64,
            color = 0xFFE4A11B
        )
    )

    fun getModules() = listOf(
        ModuleEntity(id = 1, courseId = 1, title = "Mindset & Foundation", summary = "Build the internal frame that attracts naturally", orderIndex = 0, lessonCount = 4),
        ModuleEntity(id = 2, courseId = 1, title = "Approaching & Opening", summary = "From approach anxiety to smooth conversations", orderIndex = 1, lessonCount = 4),
        ModuleEntity(id = 3, courseId = 1, title = "Building Attraction", summary = "Create chemistry that pulls her in", orderIndex = 2, lessonCount = 4),
        ModuleEntity(id = 4, courseId = 1, title = "Dating & Relationships", summary = "From first date to something real", orderIndex = 3, lessonCount = 4),
    )

    fun getLessons() = listOf(
        // Module 1: Mindset & Foundation
        LessonEntity(
            id = 1, moduleId = 1, title = "Abundance Mentality", summary = "The single most important mindset shift you'll ever make",
            body = """Abundance mentality is the foundation of all game. Without it, every interaction is poisoned by neediness.

**What is Abundance Mentality?**

It's the deep knowledge that there are plenty of women in the world, and if one doesn't work out, there will be others. This isn't about acting like you don't care — it's about genuinely knowing you'll be fine either way.

**Why It Matters**

Women are incredibly attuned to neediness. If you're coming from a place of scarcity, she'll feel it instantly. You'll over-invest, text too much, agree too easily, and put her on a pedestal. All of these are attraction killers.

**How to Build It**

1. Actually talk to more women. Not to get a date — just to normalize conversation.
2. Keep talking to other women even after you meet someone you like.
3. Have a full life outside of dating. Hobbies, career, friends, gym.
4. Remember that her time is not more valuable than yours.

**The Test**

Would you be genuinely okay if this interaction ended right now? If yes, you have abundance. If no, you're in scarcity.

Internalize: There are 4 billion women on earth. You're looking for one who's a great match, not trying to convince someone who isn't right for you.""",
            sourceUrl = null, orderIndex = 0, estimatedMinutes = 4, isCompleted = false
        ),
        LessonEntity(
            id = 2, moduleId = 1, title = "Outcome Independence", summary = "Want her but don't need her — the paradox of attraction",
            body = """Outcome independence is the ability to pursue what you want without being attached to the result. It's the single most attractive quality a man can display.

**The Paradox**

The more you need a specific outcome (her number, a kiss, a relationship), the less likely you are to get it. The more you're willing to walk away, the more she'll chase.

**Why It Works**

Outcome independence signals high status. It says: "I have options, I'm selective, and I'm not desperate." It removes the pressure from the interaction and lets genuine connection happen naturally.

**How to Practice**

- Before approaching, decide: "I'm just going to see if she's cool."
- Don't plan what you'll say. Be present and react.
- If she's not interested, genuinely don't care. Say "no worries" and move on.
- Never double text. Never chase. If she's interested, she'll show it.

**Frame Control**

You must hold your frame. Frame = your interpretation of reality. Her rejecting you isn't a reflection of your value — it's just a mismatch. You're still the prize.

**Daily Practice**

Every time you feel anxiety about what she thinks, remind yourself: "I'm enough as I am. If she doesn't see it, that's her loss, not mine.""",
            sourceUrl = null, orderIndex = 1, estimatedMinutes = 4, isCompleted = false
        ),
        LessonEntity(
            id = 3, moduleId = 1, title = "Self-Improvement is the Real Game", summary = "The best pickup line is a genuinely interesting life",
            body = """Game isn't about tricks or lines. It's about becoming a man who naturally attracts women through his lifestyle, personality, and presence.

**The Three Pillars**

1. **Body** — Lift weights. Get in shape. Dress well. Your physical presence communicates before you speak.
2. **Mind** — Read books, learn skills, develop opinions. Be someone who can talk about anything.
3. **Mission** — Have something you're working toward. A man with purpose is inherently attractive.

**Why This Matters**

Hot women have options. Every day, they get approached by guys trying to impress them. What makes you different? If your answer isn't better than "I'm a nice guy," you have work to do.

**The 90-Day Foundation**

- Hit the gym 4x/week minimum
- Read 20 pages per day
- Learn a new skill (cooking, an instrument, a language)
- Go out and socialize at least twice a week
- Cut out porn and limit social media

**Remember**

Your life is the product. Dating is just marketing. If the product isn't good, no amount of marketing will close the sale.

Focus on becoming the best version of yourself first. The rest is just a consequence.""",
            sourceUrl = null, orderIndex = 2, estimatedMinutes = 5, isCompleted = false
        ),
        LessonEntity(
            id = 4, moduleId = 1, title = "Confidence vs Arrogance", summary = "Know your worth without needing to prove it",
            body = """There's a thin line between confidence and arrogance. One attracts — the other repels. Here's how to walk it.

**Confidence**
- Speaks quietly, doesn't need validation
- Admits mistakes and weaknesses
- Laughs at himself
- Gives genuine compliments without expecting anything back
- Is comfortable in silence

**Arrogance**
- Talks loudly, name-drops, shows off
- Can't admit being wrong
- Takes himself too seriously
- Puts others down to feel superior
- Needs to fill every silence

**The Root Difference**

Confidence comes from within. It's based on your actual value as a man. Arrogance is a mask for insecurity — it's trying to convince others of value you don't believe you have.

**How to Be Confident Without Being a Douche**

- Let your actions speak. Don't tell her you're successful — let it come out naturally.
- When you don't know something, say "I don't know."
- When you mess up, own it. Don't make excuses.
- Compliment her genuinely, without expecting a return.
- Be the same person around everyone. Don't change based on status.

**The Golden Rule**

True confidence doesn't need to announce itself. If you have to say "I'm confident," you're not.""",
            sourceUrl = null, orderIndex = 3, estimatedMinutes = 4, isCompleted = false
        ),

        // Module 2: Approaching & Opening
        LessonEntity(
            id = 5, moduleId = 2, title = "The Art of the Approach", summary = "How to walk up and open your mouth without dying inside",
            body = """The approach is where most guys fail before they even start. Here's how to make it easy.

**The 3-Second Rule**

When you see someone you want to talk to, you have three seconds to start walking before your brain talks you out of it. Don't think. Just move.

**What to Say**

It literally does not matter. Here's proof:
- "Hey, I saw you and wanted to say hi."
- "This is random, but you have great style."
- "I need a second opinion — does this coffee taste off to you?"

The specific words don't matter. What matters is your tone, body language, and vibe.

**The Right Mindset**

You're not asking for her number. You're not proposing marriage. You're just seeing if she's cool. That's it. The lower the stakes, the better the outcome.

**Body Language**

- Stand up straight, shoulders back
- Hold eye contact (but don't stare)
- Speak at a normal volume — don't shout
- Keep your hands out of your pockets
- Take up space

**Common Mistakes**

- Approaching from behind (always approach from the front or side)
- Starting with an apology ("Sorry to bother you...")
- Talking too fast
- Staying too long — make your point, get the number or close, leave

**The Exit**

If it's not going well, just say "Well, it was nice meeting you" and leave. No harm, no foul. You're not in jail. You just talked to a human.""",
            sourceUrl = null, orderIndex = 0, estimatedMinutes = 5, isCompleted = false
        ),
        LessonEntity(
            id = 6, moduleId = 2, title = "Reading Body Language", summary = "What she's actually saying without words",
            body = """Words lie. Body language doesn't. Learn to read the signals.

**Positive Signals (Keep Going)**
- She turns her body fully toward you
- She plays with her hair or touches her neck
- She leans in when you speak
- She finds reasons to touch you
- Her feet point toward you
- She holds eye contact and smiles

**Negative Signals (Back Off)**
- Arms crossed (but context matters — could just be cold)
- Feet pointing toward the exit
- She's looking around the room while you talk
- She takes a step back when you step closer
- Short, clipped answers
- No follow-up questions

**The Test**

When she's talking, take a small step back. If she steps forward to close the gap, she's interested. If she stays, she's indifferent. If she also steps back, she wants space.

**Proxemics**

There are four distance zones:
- Intimate (0-18 inches) — only for people she's comfortable with
- Personal (18 inches - 4 feet) — good conversation distance
- Social (4-12 feet) — strangers
- Public (12+ feet) — everyone else

If she lets you into intimate space, she's ready for escalation.

**The Golden Signal**

Smiling + eye contact + facing you = she's interested. It's really that simple. Stop overthinking.""",
            sourceUrl = null, orderIndex = 1, estimatedMinutes = 4, isCompleted = false
        ),
        LessonEntity(
            id = 7, moduleId = 2, title = "Conversation Threading", summary = "Never run out of things to say again",
            body = """Conversation threading is the skill of turning any answer into a new topic. It makes you seem endlessly interesting to talk to.

**How It Works**

She says something. You pick one word or concept from her answer and ask about it. Repeat.

**Example**

You: "What do you do?"
Her: "I'm a graphic designer."
You: "Graphic design — that's cool. What kind of stuff do you design?"
Her: "Mostly branding for startups."
You: "Startups are a wild world. What's the most interesting one you've worked with?"

See what happened? Every answer became a new question. The conversation never dies.

**The Technique**

Listen for nouns and emotions. These are your hooks.
- Noun → "Tell me more about X."
- Emotion → "How did that make you feel?"
- Statement → "What made you get into that?"

**What Not to Do**

- Don't interrogate (question after question without sharing about yourself)
- Don't one-up ("Oh you do that? I do something better")
- Don't give one-word answers (always add something)

**The Balance**

For every question you ask, share something about yourself. This turns an interview into a conversation.

Her: "I'm a graphic designer."
You: "Nice. I've always been fascinated by design — I can barely draw a stick figure. What's your favorite project you've worked on?"

Now it's a conversation, not an interrogation.""",
            sourceUrl = null, orderIndex = 2, estimatedMinutes = 4, isCompleted = false
        ),
        LessonEntity(
            id = 8, moduleId = 2, title = "Handling Rejection", summary = "Why rejection isn't personal and how to bounce back",
            body = """Rejection is part of the game. The difference between guys who succeed and guys who don't is how they handle it.

**It's Not Personal**

She doesn't know you. She's rejecting the situation, not you as a person. Maybe she has a boyfriend. Maybe she just got fired. Maybe she's in a bad mood. You don't know, so don't assume it's about you.

**The Numbers Game**

Even the best guys get rejected. Game is a numbers game. If you approach 10 women, 7 will reject you, 2 will be neutral, and 1 will be interested. That's normal. The guy who gets the girl is the one who keeps playing despite the 7 nos.

**After Rejection**

- Don't take it personally
- Take a breath
- Analyze if there was something to learn (were you too nervous? too aggressive? too quiet?)
- Then forget it and move to the next

**When She Says No**

Respect it immediately. "No problem, have a great day." Walk away with your head up. This actually leaves a better impression than if you'd succeeded.

**The Repetition Cure**

The only cure for rejection fear is repeated exposure. Approach 10 women in a day. By number 10, you won't care about the outcome anymore. You'll be in state.

**Remember**

Every rejection is just data. Collect enough data and you'll find what works.""",
            sourceUrl = null, orderIndex = 3, estimatedMinutes = 4, isCompleted = false
        ),

        // Module 3: Building Attraction
        LessonEntity(
            id = 9, moduleId = 3, title = "The Push-Pull Dynamic", summary = "Create tension that makes her want you more",
            body = """Push-pull is a dynamic where you alternate between showing interest and pulling back. It creates emotional tension that drives attraction.

**How It Works**

Push = tease, disqualify, create distance
Pull = qualify, compliment, show interest

The alternation creates a rollercoaster of emotions. She chases the highs.

**Examples**

Pull: "You're actually really cool."
Push: "But you're probably a total nerd."
Pull: "I like that though."

Pull: "You have great energy."
Push: "It's almost too much for me to handle."
Pull: "But I think I can manage."

**Important**

This must feel natural, not like a script. The push should be playful, not mean. The pull should be genuine, not forced.

**Why It Works**

Emotionally, predictability is boring. Push-pull creates uncertainty. When she doesn't know exactly where she stands, she thinks about you more. And thinking about you = attraction.

**The 70/30 Rule**

70% warm, 30% cool. Too much push and she'll think you're an asshole. Too much pull and you'll seem needy. Keep it balanced.

**Practice**

Start with simple teasing. She says she's from New York. "Oh, so you probably think your pizza is better than everyone else's." It's playful, creates tension, and invites a response.""",
            sourceUrl = null, orderIndex = 0, estimatedMinutes = 4, isCompleted = false
        ),
        LessonEntity(
            id = 10, moduleId = 3, title = "Emotional Connection", summary = "Make her feel something — that's what she'll remember",
            body = """Women remember how you made them feel more than what you said. Emotional connection is the shortcut to deep attraction.

**The Mistake Most Guys Make**

They try to impress with logic. "I have a good job, I drive a nice car, I live in a great apartment." None of this creates attraction. It creates respect, maybe, but not desire.

**How to Create Emotional Connection**

1. **Vulnerability** — Share something real about yourself. A fear, a dream, a failure. Not on the first 5 minutes, but once rapport is built.
2. **Playfulness** — Make her laugh. Tease her. Be silly. Women want to feel like a child again when they're with you.
3. **Deep questions** — Instead of "what do you do," ask "what makes you feel alive?"
4. **Active listening** — When she shares something, reflect it back. "That sounds like it was really hard for you."

**The Escalation Ladder**

1. Surface level: Small talk, logistics
2. Opinion level: "What do you think about X?"
3. Emotional level: "How did that make you feel?"
4. Personal level: "That's really brave. I went through something similar..."

**The Goal**

By the end of the conversation, she should feel like you "get" her. Like she's known you for years. That's when attraction becomes magnetic.

**Remember**

Facts tell. Stories sell. Emotions compel.""",
            sourceUrl = null, orderIndex = 1, estimatedMinutes = 5, isCompleted = false
        ),
        LessonEntity(
            id = 11, moduleId = 3, title = "Qualification & Investment", summary = "Make her work for your attention",
            body = """Qualification is the art of making her prove herself to you. It flips the dynamic from you chasing to her chasing.

**The Principle**

When you qualify a woman, you communicate that your attention has value. She has to earn it. This makes your eventual approval much more valuable.

**How to Qualify**

Ask questions that make her demonstrate value:
- "What's something you're passionate about?"
- "Are you the adventurous type or do you play it safe?"
- "What's the coolest thing you've done this year?"

When she answers, judge her playfully:
- "Interesting answer. I'll allow it."
- "Hmm, I'm not sure I can work with that. What else you got?"

**Investment**

Investment is getting her to put effort into you. Time, attention, emotional energy. The more she invests, the more she values you.

Examples of investment:
- She asks you a question
- She explains something to you
- She teases you back
- She agrees to change locations with you

**The Investment Loop**

1. You show value (interesting story, good vibe, social proof)
2. She invests (asks a question, laughs, touches your arm)
3. You reward her investment with approval (smile, compliment, move conversation forward)
4. Repeat

**Closing**

When she's sufficiently qualified herself and invested, that's when you close. She's already decided she wants you — now you're just formalizing it.""",
            sourceUrl = null, orderIndex = 2, estimatedMinutes = 4, isCompleted = false
        ),
        LessonEntity(
            id = 12, moduleId = 3, title = "Physical Escalation", summary = "How to touch her without being creepy",
            body = """Physical touch is essential for building attraction. Without it, you're just friends. Here's how to escalate naturally.

**The Ladder**

Don't jump steps. Each rung prepares her for the next.

1. Neutral touch: Handshake, high-five, touch her arm briefly
2. Friendly touch: Hand on her shoulder, touching her back to guide her
3. Warm touch: Hand on her knee, holding her hand
4. Intimate touch: Arm around her waist, pulling her close
5. Sexual touch: Kiss, neck, lower back

**The 3-Second Rule for Touch**

When you touch her for the first time, hold it for three seconds minimum. Less than that feels accidental. Three seconds feels intentional and confident.

**Reading Her Response**

After you touch her:
- She touches you back → green light
- She doesn't move away → yellow light (proceed slowly)
- She moves away → red light (stop, rebuild rapport)

**Natural Touch Opportunities**

- "Here, let me show you something on your phone" (lean in, touch her arm)
- "You're funny" (touch her shoulder when laughing)
- Walking through a crowd (hand on her lower back)
- "Give me your hand" (palm reading, bracelet, etc.)

**The Golden Rule**

If you're unsure, escalate one step. If she pulls back, go back two steps and rebuild. If she accepts, go to the next rung.

**No Fear**

She knows why she's on a date with you. She expects you to make a move. Not escalating is worse than escalating poorly.""",
            sourceUrl = null, orderIndex = 3, estimatedMinutes = 5, isCompleted = false
        ),

        // Module 4: Dating & Relationships
        LessonEntity(
            id = 13, moduleId = 4, title = "Planning the Date", summary = "Set the stage for success before you even meet",
            body = """The date starts before you meet. Good planning sets the frame for attraction.

**The Golden Rule of First Dates**

Never do dinner for a first date. It's expensive, high pressure, and hard to exit. Do drinks or coffee instead.

**Best First Date Ideas**

1. Drinks at a cool bar — low commitment, easy to talk, easy to extend
2. Coffee + walk in a park — casual, public, creates natural movement
3. Mini golf or bowling — playful, competitive, physical touch opportunities
4. Museum or gallery — built-in conversation topics
5. A food market — variety, casual, can graze for hours

**Logistics**

- Choose a location close to your apartment (easier to pull her back)
- Have a plan for extending the date (dessert place nearby, rooftop, your place for wine)
- Know the area — don't be that guy checking Google Maps

**Time of Day**

Late afternoon -> early evening is ideal (4-7pm). It's casual enough for a drink, and if it goes well, you can suggest dinner or another activity.

**The Pre-Date Frame**

She's meeting you to see if YOU are the prize. You're also evaluating her. It's a two-way street. If she's not what you're looking for, you're allowed to walk away.

**Text Before the Date**

"Hey, I'll be at [place] around [time]. See you there."
That's it. No "are we still on?" No "I'm so excited!" You're a man with a full life. You show up. If she does too, great.""",
            sourceUrl = null, orderIndex = 0, estimatedMinutes = 4, isCompleted = false
        ),
        LessonEntity(
            id = 14, moduleId = 4, title = "The First Date Playbook", summary = "What to do minute by minute on a first date",
            body = """The first date is about building comfort, creating attraction, and leading. Here's how to nail it.

**Opening (0-5 min)**
- Hug when you meet (not a handshake)
- Compliment something specific ("I like your energy" or "you look great")
- Lead — tell her where to sit, order for both of you
- Break the touch barrier early with a brief arm touch

**Middle (5-30 min)**
- Conversation threading with humor and teasing
- Qualify her — make her earn your interest
- Share stories, not resumes
- 70% listening, 30% talking
- Physical escalation ladder (touch arm -> shoulder -> hand)

**Transition (30-40 min)**
- If it's going well: "I'm having a good time. Let's grab some food nearby."
- If it's not: "Well, this was fun. Let's do it again sometime." (you won't)
- Lead the movement — take her hand, guide her through the crowd

**Close (40-60 min)**
- If she's highly invested: kiss close
- If still building: "I'd love to see you again" and set up the next date
- Walk her to her car or ride — gentleman move that builds trust

**The Kiss**

At some point during the close, create a moment of silence. Look her in the eyes. If she holds your gaze, lean in slowly. If she pulls back, no big deal — "I wasn't going to kiss you anyway. You have something in your teeth."

**Red Flags**

- She's on her phone
- She talks about her ex
- She orders the most expensive thing
- She doesn't ask you a single question

It's okay to end the date early. Your time is valuable.""",
            sourceUrl = null, orderIndex = 1, estimatedMinutes = 5, isCompleted = false
        ),
        LessonEntity(
            id = 15, moduleId = 4, title = "Texting & Communication", summary = "Text to set dates, not to have conversations",
            body = """Texting is the death of attraction for most guys. Here's how to use it correctly.

**The Golden Rule**

Text to set dates. That's it. Don't have entire conversations over text. You build attraction in person.

**What to Text**

After the number:
- "Hey, it was cool meeting you. Let's grab drinks this week."

To confirm:
- "Thursday 8pm at [place]. See you there."

After the date:
- "Had a great time. Let's do it again."

That's all you need. Three texts. Maybe four.

**What NOT to Text**

- "Good morning beautiful" (you're not in a relationship)
- "What are you doing?" (she's living her life, not waiting for you)
- Paragraphs about your feelings (save it for in person)
- Multiple texts in a row (desperate)
- Replying instantly every time (you have a life)

**Phone Calls**

Use your voice. A 5-minute phone call builds more rapport than 50 texts. Call to set up the date. It's bold, confident, and stands out.

**Frequency**

Limit texts to 2-3 per day maximum between dates. Less is more. Let her wonder about you. Absence creates attraction.

**The Exceptions**

- If she texts you something genuinely interesting or funny, engage briefly
- If she sends a long paragraph, match her energy once, then redirect to setting the date
- If she goes cold, wait a few days, then send something playful

**Remember**

You're not a pen pal. You're a man with a mission. Texting is logistics. The magic happens face to face.""",
            sourceUrl = null, orderIndex = 2, estimatedMinutes = 4, isCompleted = false
        ),
        LessonEntity(
            id = 16, moduleId = 4, title = "Long-Term Frame", summary = "Moving from dating to a relationship without losing your frame",
            body = """Relationships require a different frame than dating. Many guys get into a relationship and immediately lose the very traits that made them attractive.

**The Trap**

Guys in relationships often:
- Stop going to the gym
- Drop their friends and hobbies
- Become overly available
- Stop leading
- Get complacent

This is how attraction dies. She fell for the guy who had a mission, a life, and options. Don't kill him.

**Maintain Your Frame**

- Keep your hobbies and friends. Your life doesn't revolve around her.
- Keep leading. Plan dates. Make decisions. Don't become passive.
- Keep your standards. You still have boundaries. You're still willing to walk away.
- Keep improving. Gym, career, skills. Never stop.

**Communication**

Address issues directly and early. Don't let resentment build. "Hey, when X happened, it made me feel Y. Can we talk about it?"

**The Most Important Thing**

A relationship should enhance your life, not become your life. The best relationships are between two complete people who choose to be together, not two halves trying to make a whole.

**Checklist for a Healthy Frame**

1. Do you still have goals outside of the relationship?
2. Are you still physically active and fit?
3. Do you still spend time with your friends?
4. Do you still lead and make decisions?
5. Are you still willing to walk away if your standards aren't met?

If you answered no to any of these, you're losing your frame. Correct it now.""",
            sourceUrl = null, orderIndex = 3, estimatedMinutes = 5, isCompleted = false
        )
    )
}

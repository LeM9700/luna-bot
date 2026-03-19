require('dotenv').config();
const { Telegraf, Markup } = require('telegraf');
const axios = require('axios');
const { encrypt, decrypt, generateKeyPair } = require('./crypto');

const bot = new Telegraf(process.env.TELEGRAM_TOKEN);

// Stockage local des sessions (en prod → Redis)
const sessions = {};

function getSession(userId) {
    if (!sessions[userId]) {
        const { publicKey, privateKey } = generateKeyPair();
        sessions[userId] = {
            companionId: 'luna',
            publicKey,
            privateKey
        };
    }
    return sessions[userId];
}

async function checkPremium(userId) {
    try {
        const resp = await axios.get(
            `${process.env.API_URL}/user/${userId}/premium`
        );
        return resp.data.is_premium;
    } catch {
        return false;
    }
}

// ── /start ────────────────────────────────────────────────────────────
bot.start((ctx) => {
    getSession(ctx.from.id);
    ctx.reply(
        `Bienvenue ! 👋 Je suis *Luna Campini*.\n\nChoisis ta partenaire :`,
        {
            parse_mode: 'Markdown',
            ...Markup.inlineKeyboard([
                [
                    Markup.button.callback('🌙 Luna — Douce', 'companion:luna'),
                    Markup.button.callback('⚡ Aria — Piquante', 'companion:aria'),
                ],
                [Markup.button.callback('🍃 Sage — Philosophique', 'companion:sage')]
            ])
        }
    );
});

// ── /switch — changer de companion (Premium uniquement) ──────────────
bot.command('switch', async (ctx) => {
    const isPrem = await checkPremium(String(ctx.from.id));

    if (!isPrem) {
        ctx.reply(
            '🔒 Changer de companion est une fonctionnalité Premium.\n\n' +
            'Tape /premium pour débloquer l\'accès.',
        );
        return;
    }

    ctx.reply(
        'Change de companion :',
        Markup.inlineKeyboard([
            [
                Markup.button.callback('🌙 Luna', 'companion:luna'),
                Markup.button.callback('⚡ Aria',  'companion:aria'),
            ],
            [Markup.button.callback('🍃 Sage', 'companion:sage')]
        ])
    );
});

// ── /memory — voir ses propres souvenirs ─────────────────────────────
bot.command('memory', async (ctx) => {
    try {
        const resp = await axios.get(
            `${process.env.API_URL}/memories/${ctx.from.id}`
        );
        const grouped = resp.data.memories;

        if (Object.keys(grouped).length === 0) {
            ctx.reply("Je n'ai pas encore de souvenirs sur toi. Parle-moi de toi ! 💬");
            return;
        }

        // Emojis par catégorie
        const icons = {
            preference:   "❤️ Préférences",
            emotion:      "💭 Émotions",
            fact:         "📌 Faits personnels",
            goal:         "🎯 Objectifs",
            relationship: "👥 Proches",
            general:      "📝 Autres"
        };

        let msg = "🧠 *Ce que je sais sur toi :*\n\n";
        for (const [cat, items] of Object.entries(grouped)) {
            const label = icons[cat] || cat;
            msg += `*${label}*\n`;
            items.forEach(item => { msg += `• ${item}\n`; });
            msg += "\n";
        }

        ctx.reply(msg, { parse_mode: 'Markdown' });

    } catch (err) {
        ctx.reply("Impossible de récupérer les souvenirs.");
    }
});


// ── /status — afficher l'état du companion ─────────────────────────────
bot.command('status', async (ctx) => {
    const userId = String(ctx.from.id);
    const session = getSession(ctx.from.id);

    try {
        const resp = await axios.get(
            `${process.env.API_URL}/companion/state/${userId}/${session.companionId}`
        );
        const s = resp.data;

        const bar = "█".repeat(Math.floor(s.attachment / 10)) +
                    "░".repeat(10 - Math.floor(s.attachment / 10));

        const names = { luna: "Luna 🌙", aria: "Aria ⚡", sage: "Sage 🍃" };

        ctx.reply(
            `*${names[session.companionId]}*\n\n` +
            `💫 Attachement : [${bar}] ${s.attachment}/100\n` +
            `🎭 Humeur : ${s.mood}\n` +
            `💬 Messages échangés : ${s.message_count}`,
            { parse_mode: 'Markdown' }
        );
    } catch {
        ctx.reply("Impossible de récupérer l'état.");
    }
});

// ── /premium — mode premium ──────────────────────────────────────────
bot.command('premium', async (ctx) => {
    const userId   = String(ctx.from.id);
    const username = ctx.from.username || ctx.from.first_name;
    const isPrem   = await checkPremium(userId);

    if (isPrem) {
        ctx.reply(
            '⭐ Tu es déjà Premium !\n\n' +
            'Tu as accès à :\n' +
            '• Les 3 companions (Luna, Aria, Sage)\n' +
            '• Mémoire long terme illimitée\n' +
            '• Génération d\'images (bientôt)'
        );
        return;
    }

    try {
        const resp = await axios.post(`${process.env.API_URL}/payment/create-checkout`, {
            user_id: userId,
            username: username
        });

        ctx.reply(
            '🌟 Passe à Luna Premium !\n\n' +
            '✓ Accès aux 3 companions\n' +
            '✓ Mémoire long terme\n' +
            '✓ 9.99€/mois — annulable à tout moment\n\n' +
            'Clique pour payer :',
            Markup.inlineKeyboard([[
                Markup.button.url('💳 Payer maintenant', resp.data.checkout_url)
            ]])
        );
    } catch (err) {
        console.error('Erreur checkout:', err.message);
        ctx.reply('Erreur lors de la création du paiement.');
    }
});

// ── Sélection companion ───────────────────────────────────────────────
bot.action(/companion:(.+)/, (ctx) => {
    const companionId = ctx.match[1];
    const session = getSession(ctx.from.id);
    session.companionId = companionId;

    const names = { luna: 'Luna 🌙', aria: 'Aria ⚡', sage: 'Sage 🍃' };
    ctx.answerCbQuery();
    ctx.reply(
        `Tu parles maintenant avec *${names[companionId]}*.\nEnvoie ton premier message !`,
        { parse_mode: 'Markdown' }
    );
});

// ── Messages texte (DOIT ÊTRE EN DERNIER) ─────────────────────────────
bot.on('text', async (ctx) => {
    const userId   = String(ctx.from.id);
    const username = ctx.from.username || ctx.from.first_name;
    const session  = getSession(ctx.from.id);
    const rawText  = ctx.message.text;

    if (rawText.startsWith('/')) return;

    await ctx.sendChatAction('typing');

    try {
        const encryptedInput = encrypt(rawText);
        console.log(`[${userId}] Message chiffré : ${encryptedInput.substring(0, 40)}...`);

        const response = await axios.post(`${process.env.API_URL}/chat`, {
            user_id:      userId,
            username:     username,
            companion_id: session.companionId,
            message:      rawText,
            public_key:   session.publicKey
        });

        const { reply, companion_name } = response.data;

        const encryptedReply = encrypt(reply);
        console.log(`[${companion_name}] Réponse chiffrée : ${encryptedReply.substring(0, 40)}...`);

        await ctx.reply(reply);

    } catch (err) {
        console.error('Erreur :', err.message);
        await ctx.reply('Une erreur est survenue. Réessaie dans un instant.');
    }
});

// ── Démarrage du bot ─────────────────────────────────────────────────
bot.launch();
console.log('🤖 Bot démarré !');

process.once('SIGINT',  () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
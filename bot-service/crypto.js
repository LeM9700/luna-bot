const crypto = require('crypto');

/**
 * Chiffrement AES-256-GCM des messages
 * Clé partagée via ENCRYPTION_KEY (hex 64 chars = 32 bytes)
 */
function encrypt(text) {
    const key    = Buffer.from(process.env.ENCRYPTION_KEY, 'hex');
    const iv     = crypto.randomBytes(12);
    const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);

    const encrypted = Buffer.concat([
        cipher.update(text, 'utf8'),
        cipher.final()
    ]);
    const tag = cipher.getAuthTag();

    return Buffer.concat([iv, tag, encrypted]).toString('base64');
}

function decrypt(data) {
    const buf       = Buffer.from(data, 'base64');
    const iv        = buf.slice(0, 12);
    const tag       = buf.slice(12, 28);
    const encrypted = buf.slice(28);
    const key       = Buffer.from(process.env.ENCRYPTION_KEY, 'hex');
    const decipher  = crypto.createDecipheriv('aes-256-gcm', key, iv);
    decipher.setAuthTag(tag);

    return Buffer.concat([
        decipher.update(encrypted),
        decipher.final()
    ]).toString('utf8');
}

/**
 * Génère une paire de clés RSA pour l'échange sécurisé
 */
function generateKeyPair() {
    const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', {
        modulusLength: 2048,
        publicKeyEncoding:  { type: 'spki',  format: 'pem' },
        privateKeyEncoding: { type: 'pkcs8', format: 'pem' }
    });
    return { publicKey, privateKey };
}

module.exports = { encrypt, decrypt, generateKeyPair };

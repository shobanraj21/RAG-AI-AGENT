from hashlib import sha256


def sha256_encoder(logger, auth_user, auth_pswd):
    try:
        enc_auth_user = sha256(auth_user.encode('utf-8')).hexdigest()
        enc_auth_pswd = sha256(auth_pswd.encode('utf-8')).hexdigest()
        logger.info(f'enc_auth_user : {enc_auth_user} \nenc_auth_pswd : {enc_auth_pswd}')
        return enc_auth_user, enc_auth_pswd
    except Exception as e:
        logger.exception(e)
        return e
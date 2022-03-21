# Configuration

## Environment Variable Settings

hunter2 has a number of configuration options exposed via environment variables.
These are best configured in a file named `.env` alongside the `docker-compose.yml`.

The following options are available for a production setup:

| Environment Variable      | Required | Description                                                                                                                  | Default     |
|---------------------------|----------|------------------------------------------------------------------------------------------------------------------------------|-------------|
| `H2_DOMAIN`               | ✔️       | The root domain for the instance (without `www.` or `event.`)                                                                |             |
| `H2_DATABASE_PASSWORD`    | ✔        | The password for the instance to connect to its database. The role must have full access to read/write the hunter2 database. |             |
| `H2_EMAIL_URL`            | ✔        | A URL of an SMTP server for sending email, eg. smtp+tls://<username>:<password>@my.email.provider:587                        |             |
| `H2_EMAIL_VERIFICATION `  | ❌        | One of 'none', 'optional' or 'mandatory' indicating whether users must verify their email address                            | 'mandatory' |
| `H2_DB_EXPORTER_PASSWORD` | ❌        | The password for database monitoring to connect to the database. The role is best setup using the installation instructions. |             |
| `H2_PIWIK_HOST`           | ❌        | The hostname of an instance of Matomo to collect analytics data                                                              |             |
| `H2_PIWIK_SITE`           | ❌        | The site number within the Matomo installation to report to                                                                  |             |
| `H2_SENTRY_DSN`           | ❌        | The URL of a Sentry DSN to report internal server errors and client JavaScript errors to                                     |             |
| `H2_SCHEME`               | ❌        | Override the scheme (protocol) in links to the site (eg. 'http' or 'https')                                                  | 'http'      |

## Admin site settings

### Static Captcha
As a basic protection against bot signups the site can be configured with a static captcha question.
The best way to use this is to think of a question which all of your attendees should know the answer to but a generic bot would not.

```{figure} img/crud_captcha.png
:width: 1200
:alt: Django admin page showing static captcha configuration

Adding a static captcha
```

# Rate limits

Version: 1.30

Rate limits are restrictions that our API imposes on the number of times a user or client can access our services within a specified period of time.

* Rate limits can be hit across any of the options depending on what occurs first.
  For example, you might send 20 requests with only 100 prompt tokens to the ChatCompletions endpoint and that would fill your limit (if your request per minute limit was 20), even if you didn't send 20k tokens (if your prompt token per minute limit was 20k) within those 20 requests.
* Rate limits are defined at the organization level, not API key level.
* Rate limits may vary by the [API](/api/overview) and [model](/models/overview) being used.

* Free
* Standard
* Enterprise

The free tier has a limited amount of prompt and completion tokens available per month.

| Limit type | Value |
| --- | --- |
| Prompt tokens | 100,000/min and 1,000,000/month |
| Completion tokens | 10,000/min and 1,000,000/month |
| Requests | 20/min |
| Audio file size | 25 MB/min and 100 MB/month |

The standard tier is a [pay-as-you-go subscription](https://www.privatemode.ai/pricing) and has no monthly usage limit.

| Limit type | Value |
| --- | --- |
| Prompt tokens | 100,000/min |
| Completion tokens | 10,000/min |
| Requests | 20/min |
| Audio file size | 25 MB/min |

For increased rate limits, please [contact us](https://www.privatemode.ai/sales).
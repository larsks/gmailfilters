# gmailfilters

A tool for managing your GMail filters that has two tricks:

1. You can manage your filters as a YAML file, which has substantially
   less markup than the XML export from GMail
2. You can specify multiple labels for a filter, and `gmailfilters`
   will automatically expand that into multiple filters, each applying
   a single label.

For example, if you have:

    - from: lars@redhat.com
      label: gmail awesome redhat

You will get, in your generated XML, something like:

    <entry>
      <title>Mail Filter</title>
      <category term="filter"/>
      <updated>2017-06-26T15:28:31.018961</updated>
      <content/>
      <app:property name="from" value="lars@redhat.com"/>
      <app:property name="label" value="gmail"/>
    </entry>
    <entry>
      <title>Mail Filter</title>
      <category term="filter"/>
      <updated>2017-06-26T15:28:31.018961</updated>
      <content/>
      <app:property name="from" value="lars@redhat.com"/>
      <app:property name="label" value="awesome"/>
    </entry>
    <entry>
      <title>Mail Filter</title>
      <category term="filter"/>
      <updated>2017-06-26T15:28:31.018961</updated>
      <content/>
      <app:property name="from" value="lars@redhat.com"/>
      <app:property name="label" value="redhat"/>
    </entry>

## Do this once (optional)

Export your GMail filters to XML:

1. Go to Settings -> Filters and Blocked Addresses
2. At the bottom of the filter list, click "All" to select all filters
3. Click the "Export" button to save your filters

Convert your filters to YAML:

    gmailfilters --fromxml mailFilters.xml -o mailFilters.yml

## Do this whenever you want to update your filters

Make changes to your YAML document (e.g. `mailFilters.yml`).

Convert your filters to XML:

    gmailfilters --toxml mailFitlers.yml -o mailFilters.xml

Delete your existing filters in GMail:

1. Go to Settings -> Filters and Blocked Addresses
2. At the bottom of the filter list, click "All" to select all filters
3. Select "Delete" to delete the filters.

Import your filters into GMail:

1. Go to Settings -> Filters and Blocked Addresses
2. At the bottom of the filter list, select "Import filters"
3. Select "Choose File" and navigate to your generated XML filters.
4. Select "Open file"
5. Scroll to the bottom of the list of filters and select "Create
   filters"

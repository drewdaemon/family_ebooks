# Some Christensens Who Came from Thy

## Manual editing process
We perform this process on computer-generated output of the OCR to
- annotate headings, quotes, and other features according to [markdown syntax](https://daringfireball.net/projects/markdown/syntax)
- correct mistakes introduced during OCR

Besides correcting obvious punctuation and character errors, make the following changes as you're reading through.

### Remove end-of-line hyphens
The book was printed with a set number of characters per line which created lots of hyphenations. 

**Example**
> to consign it to the flames of a bonfire already con-  
suming other discarded rubbish. But something

**Correction**
> to consign it to the flames of a bonfire already consuming  
> other discarded rubbish. But something

In other cases, there is a hyphen that should exist but happens to land at the end of the line. If this isn't corrected, the ebook will have an extra space in it.

**Example with an M-dash**
> fields and peoples spread out before his very eyes--  
> in ramparts of long-idle fortresses; settlements of

**Correction**
> fields and peoples spread out before his very eyes--in  
> ramparts of long-idle fortresses; settlements of

### Add missing dividers

In some places, the book includes a divider that looks like this.

`* * * * *`

Often the OCR has messed this up. Add it back in (5 asterisks).

### Page number markers

HTML `span` tags have been inserted between each page. Add in the correct page number in place of the `??`.

**Example**
> \<span id="page-??"\>\</span\>

**Correction**
> \<span id="page-56"\>\</span\>

Also, if `span` the span tag is surrounded by blank lines, remove them.

**Example**
```
some line

<span id="page-??"></span>

some line
```

**Correction**
```
some line
<span id="page-??"></span>
some line
```

Or if it is above a title, move it directly below

**Example**
```
<span id="page-??"></span>

## SOME TITLE
```

**Correction**
```
## SOME TITLE
<span id="page-??"></span>
```

### Handle quotations
Once in awhile an indented quote is included (for example at the first of a chapter).

Annotate the quote according to markdown syntax (start with `>` to begin a quote and denote line breaks with a `<br>`)

```
> "The ladies stood in Highloft <br>
their lord's return to see <br>
But every steed with blood was red, <br>
and empty each saddle-tree. <br>
The Knights bore out their shields <br>
and then must many weep"!
```
### Remove extra spaces in large numbers
**Example**
> 1, 000, 000

**Correction**
> 1,000,000



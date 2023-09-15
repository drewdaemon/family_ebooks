package main

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"strings"
)

func main() {
	// Open the text file for reading
	file, err := os.Open("grandchildren_section.txt")
	if err != nil {
		fmt.Println("Error opening file:", err)
		return
	}
	defer file.Close()

	// Create a regular expression pattern for splitting
	// You can change this regex pattern to match your separator
	regexPattern := regexp.MustCompile(`\(\d+\)((\s|\w)+)\(\d+\)`)

	// Create a scanner to read the file line by line
	scanner := bufio.NewScanner(file)

	// Initialize variables for handling sections
	var currentSection []string
	var currentSectionName string

	// Process the file and split into sections
	for scanner.Scan() {
		line := scanner.Text()

		// Check if the line matches the regex separator
		if regexPattern.MatchString(line) {
			// Write the current section to a new file
			sectionFileName := fmt.Sprintf("%s.txt", currentSectionName)
			writeSectionToFile(sectionFileName, currentSection)
			
			currentSectionName = strings.Trim(string(regexPattern.FindSubmatch([]byte(line))[1]), " ")
			fmt.Printf("%q\n", currentSectionName)

			// Reset the current section
			currentSection = nil
			currentSection = append(currentSection, line)
		} else {
			// Add the line to the current section
			currentSection = append(currentSection, line)
		}
	}


	// Check for scanner errors
	if err := scanner.Err(); err != nil {
		fmt.Println("Error reading file:", err)
	}
}

func writeSectionToFile(fileName string, lines []string) {
	// Join the lines into a single string with newlines
	sectionContent := strings.Join(lines, "\n")

	// Create or open the file for writing
	file, err := os.Create(fileName)
	if err != nil {
		fmt.Printf("Error creating file %s: %v\n", fileName, err)
		return
	}
	defer file.Close()

	// Write the section content to the file
	_, err = file.WriteString(sectionContent)
	if err != nil {
		fmt.Printf("Error writing to file %s: %v\n", fileName, err)
	}
}

